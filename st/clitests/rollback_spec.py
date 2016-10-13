#!/usr/bin/python

from framework import Config
from framework import S3PyCliTest
from s3cmd import S3cmdTest
from s3fi import S3fiTest
from jclient import JClientTest
from s3client_config import S3ClientConfig

# Helps debugging
# Config.log_enabled = True
# Config.dummy_run = True

# Set time_readable_format to False if you want to display the time in milli seconds.
# Config.time_readable_format = False

# TODO
# DNS-compliant bucket names should not contains underscore or other special characters.
# The allowed characters are [a-zA-Z0-9.-]*
#
# Add validations to S3 server and write system tests for the same.

#  ***MAIN ENTRY POINT

# Run before all to setup the test environment.
print("Configuring LDAP")
S3PyCliTest('Before_all').before_all()

# Set pathstyle =false to run jclient for partial multipart upload
S3ClientConfig.pathstyle = False
S3ClientConfig.access_key_id = 'AKIAJPINPFRBTPAYOGNA'
S3ClientConfig.secret_key = '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'

# Path style tests.
Config.config_file = "pathstyle.s3cfg"


# ************ Create bucket Fail ************
# Note: We clean kvs entries using cqlsh(cassandra-kvs) for this test to work
S3cmdTest('Deleted metadata using cqlsh').delete_metadata_test().execute_test().command_is_successful().command_is_successful()
S3fiTest('s3cmd enable FI create index fail').enable_fi("enable", "always", "clovis_idx_create_fail").execute_test().command_is_successful()
S3cmdTest('s3cmd cannot create bucket').create_bucket("seagatebucket").execute_test(negative_case=True).command_should_fail().command_error_should_have("InternalError")
S3fiTest('s3cmd disable Fault injection').disable_fi("clovis_idx_create_fail").execute_test().command_is_successful()

S3fiTest('s3cmd enable FI PUT KV').enable_fi("enable", "always", "clovis_kv_put_fail").execute_test().command_is_successful()
S3cmdTest('s3cmd cannot create bucket').create_bucket("seagatebucket").execute_test(negative_case=True).command_should_fail().command_error_should_have("InternalError")
S3fiTest('s3cmd disable Fault injection').disable_fi("clovis_kv_put_fail").execute_test().command_is_successful()
# ************ Create bucket ************
S3cmdTest('s3cmd can create bucket').create_bucket("seagatebucket").execute_test().command_is_successful()

# ************ List buckets ************
S3cmdTest('s3cmd can list buckets').list_buckets().execute_test().command_is_successful().command_response_should_have('s3://seagatebucket')

# ************ 18MB FILE Multipart Rollback TEST ***********
# function to cleanup multipart upload
def clean_18mb_multipart():
    result = S3cmdTest('s3cmd can list multipart uploads in progress').list_multipart_uploads("seagatebucket").execute_test()
    result.command_response_should_have('18MBfile')
    upload_id = result.status.stdout.split('\n')[2].split('\t')[2]
    S3cmdTest('S3cmd can abort multipart upload').abort_multipart("seagatebucket", "18MBfile", upload_id).execute_test().command_is_successful()
    return

S3fiTest('s3cmd enable FI create index fail').enable_fi("enable", "always", "clovis_idx_create_fail").execute_test().command_is_successful()
S3cmdTest('s3cmd can upload 18MB file').upload_test("seagatebucket", "18MBfile", 18000000).execute_test(negative_case=True).command_should_fail()
S3cmdTest('s3cmd should not have objects after rollback').list_objects('seagatebucket').execute_test().command_is_successful().command_response_should_not_have('18MBfile')
S3fiTest('s3cmd can disable Fault injection').disable_fi("clovis_idx_create_fail").execute_test().command_is_successful()
# Set second rollback checkpoint in multipart upload
S3fiTest('s3cmd enable FI create index fail').enable_fi_enablen("enable", "clovis_idx_create_fail", "2").execute_test().command_is_successful()
S3cmdTest('s3cmd can upload 18MB file').upload_test("seagatebucket", "18MBfile", 18000000).execute_test(negative_case=True).command_should_fail()
S3cmdTest('s3cmd should not have objects after rollback').list_objects('seagatebucket').execute_test().command_is_successful().command_response_should_not_have('18MBfile')
S3fiTest('s3cmd can disable Fault injection').disable_fi("clovis_idx_create_fail").execute_test().command_is_successful()

S3fiTest('s3cmd enable FI create index fail').enable_fi_offnonm("enable", "clovis_idx_create_fail", "1", "99").execute_test().command_is_successful()
S3cmdTest('s3cmd cannot upload 18MB file').upload_test("seagatebucket", "18MBfile", 18000000).execute_test(negative_case=True).command_should_fail().command_error_should_have("InternalError")
S3fiTest('s3cmd disable Fault injection').disable_fi("clovis_idx_create_fail").execute_test().command_is_successful()

S3fiTest('s3cmd enable FI PUT KV').enable_fi_offnonm("enable", "clovis_kv_put_fail", "2", "99").execute_test().command_is_successful()
S3cmdTest('s3cmd cannot upload 18MB file').upload_test("seagatebucket", "18MBfile", 18000000).execute_test(negative_case=True).command_should_fail().command_error_should_have("InternalError")
S3fiTest('s3cmd disable Fault injection').disable_fi("clovis_kv_put_fail").execute_test().command_is_successful()

S3fiTest('s3cmd enable FI GET KV').enable_fi_offnonm("enable", "clovis_kv_get_fail", "3", "99").execute_test().command_is_successful()
S3cmdTest('s3cmd cannot upload 18MB file').upload_test("seagatebucket", "18MBfile", 18000000).execute_test(negative_case=True).command_should_fail().command_error_should_have("InternalError")
S3fiTest('s3cmd disable Fault injection').disable_fi("clovis_kv_get_fail").execute_test().command_is_successful()
clean_18mb_multipart()

S3fiTest('s3cmd enable FI GET KV').enable_fi_offnonm("enable", "clovis_kv_get_fail", "5", "99").execute_test().command_is_successful()
S3cmdTest('s3cmd cannot upload 18MB file').upload_test("seagatebucket", "18MBfile", 18000000).execute_test(negative_case=True).command_should_fail().command_error_should_have("InternalError")
S3fiTest('s3cmd disable Fault injection').disable_fi("clovis_kv_get_fail").execute_test().command_is_successful()
clean_18mb_multipart()

S3fiTest('s3cmd enable FI GET KV').enable_fi_offnonm("enable", "clovis_kv_get_fail", "9", "99").execute_test().command_is_successful()
S3cmdTest('s3cmd cannot upload 18MB file').upload_test("seagatebucket", "18MBfile", 18000000).execute_test(negative_case=True).command_should_fail().command_error_should_have("InternalError")
S3fiTest('s3cmd disable Fault injection').disable_fi("clovis_kv_get_fail").execute_test().command_is_successful()
clean_18mb_multipart()

S3fiTest('s3cmd enable FI GET KV').enable_fi_offnonm("enable", "clovis_kv_get_fail", "20", "99").execute_test().command_is_successful()
S3cmdTest('s3cmd cannot upload 18MB file').upload_test("seagatebucket", "18MBfile", 18000000).execute_test(negative_case=True).command_should_fail().command_error_should_have("InternalError")
S3fiTest('s3cmd disable Fault injection').disable_fi("clovis_kv_get_fail").execute_test().command_is_successful()
clean_18mb_multipart()

S3fiTest('s3cmd enable FI GET KV').enable_fi_offnonm("enable", "clovis_kv_get_fail", "21", "99").execute_test().command_is_successful()
S3cmdTest('s3cmd cannot upload 18MB file').upload_test("seagatebucket", "18MBfile", 18000000).execute_test(negative_case=True).command_should_fail().command_error_should_have("InternalError")
S3fiTest('s3cmd disable Fault injection').disable_fi("clovis_kv_get_fail").execute_test().command_is_successful()
clean_18mb_multipart()

# ************  OBJ create FI ***************
S3fiTest('s3cmd enable FI Obj create').enable_fi("enable", "always", "clovis_obj_create_fail").execute_test().command_is_successful()
S3cmdTest('s3cmd cannot upload 3k file').upload_test("seagatebucket", "3kfile", 3000).execute_test(negative_case=True).command_should_fail()
S3cmdTest('s3cmd cannot upload 18MB file').upload_test("seagatebucket", "18MBfile", 18000000).execute_test(negative_case=True).command_should_fail()
S3fiTest('s3cmd disable Fault injection').disable_fi("clovis_obj_create_fail").execute_test().command_is_successful()

#*************  PUT KV FI ***************
S3fiTest('s3cmd enable FI PUT KV').enable_fi("enable", "always", "clovis_kv_put_fail").execute_test().command_is_successful()
S3cmdTest('s3cmd cannot upload 3k file').upload_test("seagatebucket", "3kfile", 3000).execute_test(negative_case=True).command_should_fail()
S3cmdTest('s3cmd cannot upload 18MB file').upload_test("seagatebucket", "18MBfile", 18000000).execute_test(negative_case=True).command_should_fail()
S3fiTest('s3cmd disable Fault injection').disable_fi("clovis_kv_put_fail").execute_test().command_is_successful()

#************** upload objects *************
S3cmdTest('s3cmd upload 3k file').upload_test("seagatebucket", "3kfile", 3000).execute_test().command_is_successful()
S3cmdTest('s3cmd upload 18MB file').upload_test("seagatebucket", "18MBfile", 18000000).execute_test().command_is_successful()

# **************** OBJ DELETE FI  ****************
S3fiTest('s3cmd enable FI OBJ Delete').enable_fi("enable", "always", "clovis_obj_delete_fail").execute_test().command_is_successful()
S3cmdTest('s3cmd cannot delete 3k file').delete_test("seagatebucket", "3kfile").execute_test(negative_case=True).command_should_fail()
S3cmdTest('s3cmd cannot delete 18MB file').delete_test("seagatebucket", "18MBfile").execute_test(negative_case=True).command_should_fail()
S3fiTest('s3cmd disable Fault injection').disable_fi("clovis_obj_delete_fail").execute_test().command_is_successful()

#**************** GET KV FI  ****************
S3fiTest('s3cmd enable FI GET KV').enable_fi("enable", "always", "clovis_kv_get_fail").execute_test().command_is_successful()
S3cmdTest('s3cmd cannot download 3k file').download_test("seagatebucket", "3kfile").execute_test(negative_case=True).command_should_fail()
S3cmdTest('s3cmd cannot download 18MB file').download_test("seagatebucket", "18MBfile").execute_test(negative_case=True).command_should_fail()
S3fiTest('s3cmd disable Fault injection').disable_fi("clovis_kv_get_fail").execute_test().command_is_successful()

# ************ Multiple Delete bucket TEST ************
file_name = "3kfile"
for num in range(0, 2):
  new_file_name = '%s%d' % (file_name, num)
  S3cmdTest('s3cmd can upload 3k file').upload_test("seagatebucket", new_file_name, 3000).execute_test().command_is_successful()

S3fiTest('s3cmd enable fail_fetch_bucket_info').enable_fi("enable", "always", "fail_fetch_bucket_info").execute_test().command_is_successful()
S3cmdTest('s3cmd cannot delete multiple objects').multi_delete_test("seagatebucket").execute_test(negative_case=True).command_should_fail().command_error_should_have("InternalError")
S3fiTest('s3cmd disable Fault injection').disable_fi("fail_fetch_bucket_info").execute_test().command_is_successful()

S3fiTest('s3cmd enable fail_fetch_objects_info').enable_fi("enable", "always", "fail_fetch_objects_info").execute_test().command_is_successful()
S3cmdTest('s3cmd cannot delete multiple objects').multi_delete_test("seagatebucket").execute_test(negative_case=True).command_should_fail().command_error_should_have("InternalError")
S3fiTest('s3cmd disable Fault injection').disable_fi("fail_fetch_objects_info").execute_test().command_is_successful()

S3fiTest('s3cmd enable fail_delete_objects_metadata').enable_fi("enable", "always", "fail_delete_objects_metadata").execute_test().command_is_successful()
S3cmdTest('s3cmd cannot delete multiple objects').multi_delete_test("seagatebucket").execute_test(negative_case=True).command_should_fail().command_error_should_have("InternalError")
S3fiTest('s3cmd disable Fault injection').disable_fi("fail_delete_objects_metadata").execute_test().command_is_successful()

S3cmdTest('s3cmd can delete multiple objects').multi_delete_test("seagatebucket").execute_test().command_is_successful().command_response_should_have('delete: \'s3://seagatebucket/3kfile0\'').command_response_should_have('delete: \'s3://seagatebucket/3kfile1\'')

# ************ Cleanup bucket + Object  ************
S3cmdTest('s3cmd can delete bucket').delete_bucket("seagatebucket").execute_test().command_is_successful()

# ******************* multipart and partial parts *********************
S3cmdTest('s3cmd can create bucket').create_bucket("seagatebucket").execute_test().command_is_successful()
S3fiTest('s3cmd enable FI Obj create').enable_fi("enable", "always", "clovis_obj_create_fail").execute_test().command_is_successful()
JClientTest('Jclient cannot upload partial parts.').partial_multipart_upload("seagatebucket", "18MBfile", 18000000, 1, 2).execute_test(negative_case=True).command_should_fail()
S3fiTest('s3cmd disable Fault injection').disable_fi("clovis_obj_create_fail").execute_test().command_is_successful()

S3fiTest('s3cmd enable FI PUT KV').enable_fi("enable", "always", "clovis_kv_put_fail").execute_test().command_is_successful()
JClientTest('Jclient cannot upload partial parts.').partial_multipart_upload("seagatebucket", "18MBfile", 18000000, 1, 2).execute_test(negative_case=True).command_should_fail()
S3fiTest('s3cmd disable Fault injection').disable_fi("clovis_kv_put_fail").execute_test().command_is_successful()

JClientTest('Jclient can upload partial parts to test abort and list multipart.').partial_multipart_upload("seagatebucket", "18MBfile", 18000000, 1, 2).execute_test().command_is_successful()

S3fiTest('s3cmd enable FI GET KV').enable_fi("enable", "always", "clovis_kv_get_fail").execute_test().command_is_successful()
S3cmdTest('s3cmd cannot list multipart uploads in progress').list_multipart_uploads("seagatebucket").execute_test(negative_case=True).command_should_fail()
S3fiTest('s3cmd disable Fault injection').disable_fi("clovis_kv_get_fail").execute_test().command_is_successful()
result = S3cmdTest('s3cmd can list multipart uploads in progress').list_multipart_uploads("seagatebucket").execute_test()
result.command_response_should_have('18MBfile')
upload_id = result.status.stdout.split('\n')[2].split('\t')[2]

S3fiTest('s3cmd enable FI GET KV').enable_fi("enable", "always", "clovis_kv_get_fail").execute_test().command_is_successful()
result = S3cmdTest('S3cmd cannot list parts of multipart upload.').list_parts("seagatebucket", "18MBfile", upload_id).execute_test(negative_case=True).command_should_fail()
S3fiTest('s3cmd disable Fault injection').disable_fi("clovis_kv_get_fail").execute_test().command_is_successful()

S3fiTest('s3cmd enable FI GET KV').enable_fi_offnonm("enable", "clovis_kv_get_fail", "4", "99").execute_test().command_is_successful()
result = S3cmdTest('S3cmd cannot list parts of multipart upload.').list_parts("seagatebucket", "18MBfile", upload_id).execute_test(negative_case=True).command_should_fail()
S3fiTest('s3cmd disable Fault injection').disable_fi("clovis_kv_get_fail").execute_test().command_is_successful()
S3fiTest('s3cmd enable FI GET KV').enable_fi("enable", "always", "clovis_kv_get_fail").execute_test().command_is_successful()
S3cmdTest('S3cmd cannot abort multipart upload').abort_multipart("seagatebucket", "18MBfile", upload_id).execute_test(negative_case=True).command_should_fail()
S3fiTest('s3cmd disable Fault injection').disable_fi("clovis_kv_get_fail").execute_test().command_is_successful()
S3cmdTest('S3cmd can abort multipart upload').abort_multipart("seagatebucket", "18MBfile", upload_id).execute_test().command_is_successful()

S3cmdTest('s3cmd can test the multipart was aborted.').list_multipart_uploads('seagatebucket').execute_test().command_is_successful().command_response_should_not_have('18MBfile')
S3cmdTest('s3cmd can delete bucket').delete_bucket("seagatebucket").execute_test().command_is_successful()
# ******************************************************************

# *************** Unused FI APIs above *************
# NOTE: Remove FI API if they are used in any test above in future
S3fiTest('s3cmd enable FI random test').enable_fi_random("enable", "unused_fail", "10").execute_test().command_is_successful()
S3fiTest('s3cmd disable Fault injection').disable_fi("unused_fail").execute_test().command_is_successful()
S3fiTest('s3cmd enable FI offnonm test').enable_fi_offnonm("enable", "unused_fail", "3", "5").execute_test().command_is_successful()
S3fiTest('s3cmd disable Fault injection').disable_fi("unused_fail").execute_test().command_is_successful()
S3fiTest('s3cmd enable FI once test').enable_fi("enable", "once", "unused_fail").execute_test().command_is_successful()
S3fiTest('s3cmd disable Fault injection').disable_fi("unused_fail").execute_test().command_is_successful()

# ************ Negative ACL/Policy TESTS ************
S3cmdTest('s3cmd can create bucket').create_bucket("seagatebucket").execute_test().command_is_successful()
S3cmdTest('s3cmd can upload 3k file with default acl').upload_test("seagatebucket", "3kfile", 3000).execute_test().command_is_successful()
S3fiTest('s3cmd enable FI PUT KV').enable_fi("enable", "always", "clovis_kv_put_fail").execute_test().command_is_successful()
S3cmdTest('s3cmd cannot set acl on bucket').setacl_bucket("seagatebucket","read:123").execute_test(negative_case=True).command_should_fail()
S3cmdTest('s3cmd cannot set acl on object').setacl_object("seagatebucket","3kfile", "read:123").execute_test(negative_case=True).command_should_fail()
S3cmdTest('s3cmd cannot revoke acl on bucket').revoke_acl_bucket("seagatebucket","read:123").execute_test(negative_case=True).command_should_fail()
S3cmdTest('s3cmd cannot revoke acl on object').revoke_acl_object("seagatebucket","3kfile","read:123").execute_test(negative_case=True).command_should_fail()
S3cmdTest('s3cmd cannot set policy on bucket').setpolicy_bucket("seagatebucket","policy.txt").execute_test(negative_case=True).command_should_fail()
S3cmdTest('s3cmd can set policy on bucket').delpolicy_bucket("seagatebucket").execute_test(negative_case=True).command_should_fail()
S3fiTest('s3cmd disable Fault injection').disable_fi("clovis_kv_put_fail").execute_test().command_is_successful()
S3cmdTest('s3cmd can delete 3kfile after setting acl').delete_test("seagatebucket", "3kfile").execute_test().command_is_successful()
S3cmdTest('s3cmd can delete bucket after setting policy/acl').delete_bucket("seagatebucket").execute_test().command_is_successful()
# ************************************************

# Path style tests.
pathstyle_values = [True, False]
for i, val in enumerate(pathstyle_values):
    S3ClientConfig.pathstyle = val
    print("\nPath style = " + str(val) + "\n")

    # ************ Create bucket ************
    JClientTest('Jclient can create bucket').create_bucket("seagatebucket").execute_test().command_is_successful()

    # ************ List buckets ************
    JClientTest('Jclient can list buckets').list_buckets().execute_test().command_is_successful().command_response_should_have('seagatebucket')

    # ************ 8k FILE TEST ************
    S3fiTest('s3cmd enable FI create index fail').enable_fi("enable", "always", "clovis_idx_create_fail").execute_test().command_is_successful()
    JClientTest('Jclient can upload 8k file').put_object("seagatebucket", "8kfile", 8192).execute_test(negative_case=True).command_should_fail()

    JClientTest('Jclient should not have object after rollback').list_objects('seagatebucket').execute_test().command_is_successful().command_response_should_not_have('8kfile')
    S3fiTest('s3cmd can disable Fault injection').disable_fi("clovis_idx_create_fail").execute_test().command_is_successful()

    # ************ OBJ Create FI: CHUNK UPLOAD ************
    S3fiTest('S3Fi enable FI Obj create').enable_fi("enable", "always", "clovis_obj_create_fail")\
            .execute_test().command_is_successful()

    JClientTest('JClient cannot upload 3k file').put_object("seagatebucket", "3kfile", 3000, chunked=True)\
            .execute_test(negative_case=True).command_should_fail().command_error_should_have("InternalError")

    JClientTest('JClient cannot upload 18MB file').put_object("seagatebucket", "18MBfile", 18000000, chunked=True)\
            .execute_test(negative_case=True).command_should_fail().command_error_should_have("InternalError")

    S3fiTest('S3Fi disable Fault injection').disable_fi("clovis_obj_create_fail").execute_test().command_is_successful()


    # ************ OBJ Write FI: CHUNK UPLOAD ************
    S3fiTest('S3Fi enable FI Obj write').enable_fi("enable", "always", "clovis_obj_write_fail")\
            .execute_test().command_is_successful()

    JClientTest('JClient cannot upload 3k file').put_object("seagatebucket", "3kfile", 3000, chunked=True)\
            .execute_test(negative_case=True).command_should_fail().command_error_should_have("InternalError")

    JClientTest('JClient cannot upload 18MB file').put_object("seagatebucket", "18MBfile", 18000000, chunked=True)\
            .execute_test(negative_case=True).command_should_fail()

    S3fiTest('S3Fi disable Fault injection').disable_fi("clovis_obj_write_fail").execute_test().command_is_successful()


    # ************ OBJ Create FI: Multipart ************
    S3fiTest('S3Fi enable FI Obj create').enable_fi("enable", "always", "clovis_obj_create_fail")\
            .execute_test().command_is_successful()

    JClientTest('JClient cannot upload 18MB file (Multipart)').put_object_multipart("seagatebucket", "18MBfile", 18000000, 15)\
            .execute_test(negative_case=True).command_should_fail().command_error_should_have("InternalError")

    S3fiTest('S3Fi disable Fault injection').disable_fi("clovis_obj_create_fail").execute_test().command_is_successful()


    # ************ OBJ Write FI: Multipart ************
    S3fiTest('S3Fi enable FI Obj write').enable_fi("enable", "always", "clovis_obj_write_fail")\
            .execute_test().command_is_successful()

    JClientTest('JClient cannot upload 18MB file (Multipart)').put_object_multipart("seagatebucket", "18MBfile", 18000000, 15)\
            .execute_test(negative_case=True).command_should_fail().command_error_should_have("Multipart upload failed")

    JClientTest('JClient cannot upload 18MB file (Multipart)').put_object_multipart("seagatebucket", "18MBfile", 18000000, 15, chunked=True)\
            .execute_test(negative_case=True).command_should_fail().command_error_should_have("Multipart upload failed")

    S3fiTest('S3Fi disable Fault injection').disable_fi("clovis_obj_write_fail").execute_test().command_is_successful()


    # ************ Partial Multipart Upload ************
    JClientTest('JClient can upload parts of 18MB file').partial_multipart_upload("seagatebucket", "18MBfile", 18000000, 5, 2)\
            .execute_test().command_is_successful()

    # ************ OBJ LIST FI: Partial Multipart ************
    result = JClientTest('Jclient can list all multipart uploads.').list_multipart("seagatebucket").execute_test()
    result.command_response_should_have('18MBfile')
    upload_id = result.status.stdout.split("id - ")[1]
    print(upload_id)

    S3fiTest('S3Fi enable FI get KV').enable_fi("enable", "always", "clovis_kv_get_fail").execute_test()

    JClientTest('Jclient cannot list all multipart uploads.').list_multipart("seagatebucket")\
            .execute_test(negative_case=True).command_should_fail().command_error_should_have("InternalError")

    JClientTest('Jclient cannot list parts of multipart upload.').list_parts("seagatebucket", "18MBfile", upload_id)\
            .execute_test(negative_case=True).command_should_fail().command_error_should_have("NoSuchBucket")

    S3fiTest('S3Fi disable Fault injection').disable_fi("clovis_kv_get_fail").execute_test().command_is_successful()


    # ************ OBJ DELETE FI: Multipart ************
    S3fiTest('S3Fi enable FI delete').enable_fi("enable", "always", "clovis_obj_delete_fail")\
            .execute_test().command_is_successful()

    JClientTest('Jclient cannot abort multipart upload.').abort_multipart("seagatebucket", "18MBfile", upload_id)\
            .execute_test(negative_case=True).command_should_fail().command_error_should_have("InternalError")

    S3fiTest('S3Fi disable Fault injection').disable_fi("clovis_obj_delete_fail").execute_test().command_is_successful()


    """
    # ************ Abort multipart upload ************
    JClientTest('Jclient can abort multipart upload.').abort_multipart("seagatebucket", "18MBfile", upload_id)\
            .execute_test().command_is_successful()
    """

    # ************ Delete bucket TEST ************
    JClientTest('Jclient can delete bucket').delete_bucket("seagatebucket").execute_test().command_is_successful()
