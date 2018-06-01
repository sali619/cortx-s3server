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
 * Original author:  Rajesh Nambiar   <rajesh.nambiar@seagate.com>
 * Original creation date: 1-Oct-2015
 */

#include "s3_uri_to_mero_oid.h"
#include "fid/fid.h"
#include "murmur3_hash.h"
#include "s3_common.h"
#include "s3_log.h"
#include "s3_perf_logger.h"
#include "s3_stats.h"
#include "s3_timer.h"

void S3UriToMeroOID(const char* name, struct m0_uint128* object_id,
                    S3ClovisEntityType type) {
  s3_log(S3_LOG_DEBUG, "", "Entering\n");

  /* MurMur Hash */
  S3Timer timer;
  timer.start();
  size_t len = 0;
  uint64_t hash128_64[2];
  struct m0_uint128 tmp_uint128;
  struct m0_fid index_fid;

  object_id->u_hi = object_id->u_lo = 0;
  if (name == NULL) {
    s3_log(S3_LOG_ERROR, "", "The input parameter 'name' is NULL\n");
    return;
  }

  len = strlen(name);
  if (len == 0) {
    // oid should not be 0
    s3_log(S3_LOG_ERROR, "", "The input parameter 'name' is empty string\n");
    return;
  }
  MurmurHash3_x64_128(name, len, 0, &hash128_64);

  //
  // Reset the higher 37 bits, will be used by Mero
  // The lower 91 bits used by S3
  // https://jts.seagate.com/browse/CASTOR-2155

  hash128_64[0] = hash128_64[0] & 0x0000000007ffffff;
  tmp_uint128.u_hi = hash128_64[0];
  tmp_uint128.u_lo = hash128_64[1];

  // Ensure OID does not fall in clovis and S3 reserved range.
  struct m0_uint128 s3_range = {0ULL, 0ULL};
  s3_range.u_lo = S3_OID_RESERVED_COUNT;

  struct m0_uint128 reserved_range = {0ULL, 0ULL};
  m0_uint128_add(&reserved_range, &M0_CLOVIS_ID_APP, &s3_range);

  int rc = m0_uint128_cmp(&reserved_range, &tmp_uint128);
  if (rc >= 0) {
    struct m0_uint128 res;
    // ID should be more than M0_CLOVIS_ID_APP
    s3_log(S3_LOG_DEBUG, "",
           "Id from Murmur hash algorithm less than M0_CLOVIS_ID_APP\n");
    m0_uint128_add(&res, &reserved_range, &tmp_uint128);
    tmp_uint128.u_hi = res.u_hi;
    tmp_uint128.u_lo = res.u_lo;
    tmp_uint128.u_hi = tmp_uint128.u_hi & 0x0000000007ffffff;
  }
  if (type == S3ClovisEntityType::index) {
    index_fid = M0_FID_TINIT('x', tmp_uint128.u_hi, tmp_uint128.u_lo);
    tmp_uint128.u_hi = index_fid.f_container;
    tmp_uint128.u_lo = index_fid.f_key;
  }

  *object_id = tmp_uint128;
  s3_log(S3_LOG_DEBUG, "", "ID for %s is %lu %lu\n", name, object_id->u_hi,
         object_id->u_lo);

  timer.stop();
  LOG_PERF("S3UriToMeroOID_ns", timer.elapsed_time_in_nanosec());
  s3_stats_timing("uri_to_mero_oid", timer.elapsed_time_in_millisec());

  s3_log(S3_LOG_DEBUG, "", "Exiting\n");
  return;
}
