/*
 * COPYRIGHT 2015 SEAGATE LLC
 *
 * THIS DRAWING/DOCUMENT, ITS SPECIFICATIONS, AND THE DATA CONTAINED
 * HEREIN, ARE THE EXCLUSIVE PROPERTY OF SEAGATE TECHNOLOGY
 * LIMITED, ISSUED IN STRICT CONFIDENCE AND SHALL NOT, WITHOUT
 * THE PRIOR WRITTEN PERMISSION OF SEAGATE TECHNOLOGY LIMITED,
 * BE REPRODUCED, COPIED, OR DISCLOSED TO A THIRD PARTY, OR
 * USED FOR ANY PURPOSE WHATSOEVER, OR STORED IN A RETRIEVAL SYSTEM
 * EXCEPT AS ALLOWED BY THE TERMS OF SEAGATE LICENSES AND AGREEMENTS.
 *
 * YOU SHOULD HAVE RECEIVED A COPY OF SEAGATE'S LICENSE ALONG WITH
 * THIS RELEASE. IF NOT PLEASE CONTACT A SEAGATE REPRESENTATIVE
 * http://www.seagate.com/contact
 *
 * Original author:  Kaustubh Deorukhkar   <kaustubh.deorukhkar@seagate.com>
 * Original creation date: 1-Oct-2015
 */

#include "s3_put_object_action.h"
#include "s3_option.h"
#include "s3_error_codes.h"
#include "s3_perf_logger.h"
#include "s3_uri_to_mero_oid.h"
#include "s3_log.h"

#define MAX_COLLISION_TRY 20

S3PutObjectAction::S3PutObjectAction(std::shared_ptr<S3RequestObject> req) : S3Action(req), total_data_to_stream(0), write_in_progress(false) {
  s3_log(S3_LOG_DEBUG, "Constructor\n");
  S3UriToMeroOID(request->get_object_uri().c_str(), &oid);
  tried_count = 0;
  salt = "uri_salt_";
  setup_steps();
}

void S3PutObjectAction::setup_steps(){
  s3_log(S3_LOG_DEBUG, "Setting up the action\n");
  add_task(std::bind( &S3PutObjectAction::fetch_bucket_info, this ));
  add_task(std::bind( &S3PutObjectAction::create_object, this ));
  add_task(std::bind( &S3PutObjectAction::initiate_data_streaming, this ));
  add_task(std::bind( &S3PutObjectAction::save_metadata, this ));
  add_task(std::bind( &S3PutObjectAction::send_response_to_s3_client, this ));
  // ...
}

void S3PutObjectAction::fetch_bucket_info() {
  s3_log(S3_LOG_DEBUG, "Entering\n");
  if (!request->get_buffered_input().is_freezed()) {
    request->pause();  // Pause reading till we are ready to consume data.
  }
  bucket_metadata = std::make_shared<S3BucketMetadata>(request);
  bucket_metadata->load(std::bind( &S3PutObjectAction::next, this), std::bind( &S3PutObjectAction::next, this));
  s3_log(S3_LOG_DEBUG, "Exiting\n");
}

void S3PutObjectAction::create_object() {
  s3_log(S3_LOG_DEBUG, "Entering\n");
  if (bucket_metadata->get_state() == S3BucketMetadataState::present) {
    create_object_timer.start();
    clovis_writer = std::make_shared<S3ClovisWriter>(request, oid);
    clovis_writer->create_object(std::bind( &S3PutObjectAction::next, this), std::bind( &S3PutObjectAction::create_object_failed, this));
  } else {
    s3_log(S3_LOG_WARN, "Bucket [%s] not found\n", request->get_bucket_name().c_str());
    request->resume();
    send_response_to_s3_client();
  }
  s3_log(S3_LOG_DEBUG, "Exiting\n");
}

void S3PutObjectAction::create_object_failed() {
  s3_log(S3_LOG_DEBUG, "Entering\n");
  if (clovis_writer->get_state() == S3ClovisWriterOpState::exists) {
    // If object exists, it may be due to the actual existance of object or due to oid collision
    if (tried_count) { // No need of lookup of metadata in case if it was oid collision before
      collision_detected();
    } else {
       object_metadata = std::make_shared<S3ObjectMetadata>(request);
       // Lookup metadata, if the object doesn't exist then its collision, do collision resolution
       // If object exist in metadata then we overwrite it
       object_metadata->load(std::bind( &S3PutObjectAction::next, this), std::bind( &S3PutObjectAction::collision_detected, this));
    }
  } else {
    create_object_timer.stop();
    LOG_PERF("create_object_failed_ms", create_object_timer.elapsed_time_in_millisec());
    s3_log(S3_LOG_WARN, "Create object failed.\n");

    request->resume();
    // Any other error report failure.
    send_response_to_s3_client();
  }
  s3_log(S3_LOG_DEBUG, "Exiting\n");
}

void S3PutObjectAction::collision_detected() {
  if(object_metadata->get_state() == S3ObjectMetadataState::missing && tried_count < MAX_COLLISION_TRY) {
    s3_log(S3_LOG_INFO, "Object ID collision happened for uri %s\n", request->get_object_uri().c_str());
    // Handle Collision
    create_new_oid();
    tried_count++;
    if (tried_count > 5) {
      s3_log(S3_LOG_INFO, "Object ID collision happened %d times for uri %s\n", tried_count, request->get_object_uri().c_str());
    }
    create_object();
  } else {
    if (tried_count > MAX_COLLISION_TRY) {
      s3_log(S3_LOG_ERROR, "Failed to resolve object id collision %d times for uri %s\n",
             tried_count, request->get_object_uri().c_str());
    }
    request->resume();
    send_response_to_s3_client();
  }
}

void S3PutObjectAction::create_new_oid() {
  std::string salted_uri = request->get_object_uri() + salt + std::to_string(tried_count);
  S3UriToMeroOID(salted_uri.c_str(), &oid);
  return;
}


void S3PutObjectAction::initiate_data_streaming() {
  s3_log(S3_LOG_DEBUG, "Entering\n");
  create_object_timer.stop();
  LOG_PERF("create_object_successful_ms", create_object_timer.elapsed_time_in_millisec());

  total_data_to_stream = request->get_content_length();
  request->resume();

  if (total_data_to_stream == 0) {
    save_metadata();  // Zero size object.
  } else {
    if (request->has_all_body_content()) {
      s3_log(S3_LOG_DEBUG, "We have all the data, so just write it.\n");
      write_object(request->get_buffered_input());
    } else {
      s3_log(S3_LOG_DEBUG, "We do not have all the data, start listening...\n");
      // Start streaming, logically pausing action till we get data.
      request->listen_for_incoming_data(
          std::bind(&S3PutObjectAction::consume_incoming_content, this),
          S3Option::get_instance()->get_clovis_write_payload_size()
        );
    }
  }
  s3_log(S3_LOG_DEBUG, "Exiting\n");
}

void S3PutObjectAction::consume_incoming_content() {
  s3_log(S3_LOG_DEBUG, "Entering\n");
  // Resuming the action since we have data.
  if (!write_in_progress) {
    if (request->get_buffered_input().is_freezed() ||
        request->get_buffered_input().length() > S3Option::get_instance()->get_clovis_write_payload_size()) {
      write_object(request->get_buffered_input());
    }
  }
  if (!request->get_buffered_input().is_freezed() &&
      request->get_buffered_input().length() >=
      (S3Option::get_instance()->get_clovis_write_payload_size() * S3Option::get_instance()->get_read_ahead_multiple())) {
    s3_log(S3_LOG_DEBUG, "Pausing with Buffered length = %zu\n", request->get_buffered_input().length());
    request->pause();
  }
  s3_log(S3_LOG_DEBUG, "Exiting\n");
}

void S3PutObjectAction::write_object(S3AsyncBufferContainer& buffer) {
  s3_log(S3_LOG_DEBUG, "Entering\n");

  clovis_writer->write_content(std::bind( &S3PutObjectAction::write_object_successful, this), std::bind( &S3PutObjectAction::write_object_failed, this), buffer);

  write_in_progress = true;
  s3_log(S3_LOG_DEBUG, "Exiting\n");
}

void S3PutObjectAction::write_object_successful() {
  s3_log(S3_LOG_DEBUG, "Write to clovis successful\n");
  write_in_progress = false;
  if (/* buffered data len is at least equal to max we can write to clovis in one write */
      request->get_buffered_input().length() > S3Option::get_instance()->get_clovis_write_payload_size()
      || /* we have all the data buffered and ready to write */
      (request->get_buffered_input().is_freezed() && request->get_buffered_input().length() > 0)) {
    write_object(request->get_buffered_input());
  } else if (request->get_buffered_input().is_freezed() && request->get_buffered_input().length() == 0) {
    next();
  } // else we wait for more incoming data
  request->resume();
  s3_log(S3_LOG_DEBUG, "Exiting\n");
}

void S3PutObjectAction::write_object_failed() {
  s3_log(S3_LOG_WARN, "Failed writing to clovis.\n");
  write_in_progress = false;
  request->resume();
  send_response_to_s3_client();
}

void S3PutObjectAction::save_metadata() {
  s3_log(S3_LOG_DEBUG, "Entering\n");
  // xxx set attributes & save
  object_metadata = std::make_shared<S3ObjectMetadata>(request);
  object_metadata->set_content_length(request->get_data_length_str());
  object_metadata->set_md5(clovis_writer->get_content_md5());
  object_metadata->set_oid(clovis_writer->get_oid());
  for (auto it: request->get_in_headers_copy()) {
    if (it.first.find("x-amz-meta-") != std::string::npos) {
      s3_log(S3_LOG_DEBUG, "Writing user metadata on object: [%s] -> [%s]\n",
          it.first.c_str(), it.second.c_str());
      object_metadata->add_user_defined_attribute(it.first, it.second);
    }
  }
  object_metadata->save(std::bind( &S3PutObjectAction::next, this), std::bind( &S3PutObjectAction::next, this));
  s3_log(S3_LOG_DEBUG, "Exiting\n");
}

void S3PutObjectAction::send_response_to_s3_client() {
  s3_log(S3_LOG_DEBUG, "Entering\n");

  if (bucket_metadata->get_state() == S3BucketMetadataState::missing) {
    // Invalid Bucket Name
    S3Error error("NoSuchBucket", request->get_request_id(), request->get_object_uri());
    std::string& response_xml = error.to_xml();
    request->set_out_header_value("Content-Type", "application/xml");
    request->set_out_header_value("Content-Length", std::to_string(response_xml.length()));

    request->send_response(error.get_http_status_code(), response_xml);
  } else if (clovis_writer && clovis_writer->get_state() == S3ClovisWriterOpState::failed) {
    S3Error error("InternalError", request->get_request_id(), request->get_object_uri());
    std::string& response_xml = error.to_xml();
    request->set_out_header_value("Content-Type", "application/xml");
    request->set_out_header_value("Content-Length", std::to_string(response_xml.length()));

    request->send_response(error.get_http_status_code(), response_xml);
  } else if (object_metadata && object_metadata->get_state() == S3ObjectMetadataState::saved) {
    request->set_out_header_value("ETag", clovis_writer->get_content_md5());

    request->send_response(S3HttpSuccess200);
  } else {
    S3Error error("InternalError", request->get_request_id(), request->get_object_uri());
    std::string& response_xml = error.to_xml();
    request->set_out_header_value("Content-Type", "application/xml");
    request->set_out_header_value("Content-Length", std::to_string(response_xml.length()));

    request->send_response(error.get_http_status_code(), response_xml);
  }
  request->resume();

  done();
  i_am_done();  // self delete
  s3_log(S3_LOG_DEBUG, "Exiting\n");
}
