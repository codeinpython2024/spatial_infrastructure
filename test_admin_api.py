import unittest
import json
from main import app
from database import get_db_connection, release_db_connection

class AdminApiTestCase(unittest.TestCase):
    def setUp(self):
        # Configure app for testing
        app.config['TESTING'] = True
        self.client = app.test_client()
        
        # Log in the test client by setting session['logged_in'] = True
        with self.client.session_transaction() as sess:
            sess['logged_in'] = True
            
        self.test_asset_ids = []

    def tearDown(self):
        # Clean up any created assets
        if self.test_asset_ids:
            conn = get_db_connection()
            if conn:
                try:
                    with conn.cursor() as cursor:
                        for asset_id in self.test_asset_ids:
                            cursor.execute("DELETE FROM infrastructure_assets WHERE id = %s AND source = 'Admin Portal';", (asset_id,))
                        conn.commit()
                except Exception as e:
                    print(f"Error in tearDown cleanup: {e}")
                    conn.rollback()
                finally:
                    release_db_connection(conn)

    def test_lga_proximity_check_and_override(self):
        # 1. Add asset close to Alimosho (e.g. Orisunbare PHC is at Lat: 6.5699, Lon: 3.3030)
        # Coordinates very close (distance ~ 0 km)
        payload_close = {
            "asset_name": "Test Close Asset",
            "asset_type": "healthcare",
            "sub_type": "Clinic",
            "state": "Lagos",
            "lga": "Alimosho",
            "lat": "6.570",
            "lon": "3.303",
            "override_duplicate_check": True
        }
        
        response = self.client.post('/api/v1/admin/add-asset', 
                                    data=json.dumps(payload_close),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertTrue(data.get("success"))
        asset_id = data["asset"]["id"]
        self.test_asset_ids.append(asset_id)
        
        # 2. Add asset far from Alimosho assets (>25km away, using Abuja coordinates)
        # Without override_lga_check
        payload_far = {
            "asset_name": "Test Far Asset",
            "asset_type": "healthcare",
            "sub_type": "Clinic",
            "state": "Lagos",
            "lga": "Alimosho",
            "lat": "9.0820", # Abuja
            "lon": "7.5333"
        }
        
        response = self.client.post('/api/v1/admin/add-asset', 
                                    data=json.dumps(payload_far),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data.get("lga_warning"))
        self.assertIn("distance_km", data)
        self.assertGreater(data["distance_km"], 25.0)
        
        # 3. Add asset far from Alimosho assets WITH override_lga_check=True
        payload_far_override = payload_far.copy()
        payload_far_override["override_lga_check"] = True
        
        response = self.client.post('/api/v1/admin/add-asset', 
                                    data=json.dumps(payload_far_override),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertTrue(data.get("success"))
        far_asset_id = data["asset"]["id"]
        self.test_asset_ids.append(far_asset_id)
        
        # 4. Edit the asset: move it to another out-of-bounds location without override
        payload_edit_far = {
            "asset_name": "Updated Far Asset",
            "asset_type": "healthcare",
            "sub_type": "Clinic",
            "state": "Lagos",
            "lga": "Alimosho",
            "lat": "9.0500", # another far point
            "lon": "7.5000"
        }
        
        response = self.client.post(f'/api/v1/admin/edit-asset/{far_asset_id}', 
                                    data=json.dumps(payload_edit_far),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data.get("lga_warning"))
        
        # 5. Edit the asset WITH override
        payload_edit_far_override = payload_edit_far.copy()
        payload_edit_far_override["override_lga_check"] = True
        
        response = self.client.post(f'/api/v1/admin/edit-asset/{far_asset_id}', 
                                    data=json.dumps(payload_edit_far_override),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data.get("success"))
        self.assertEqual(data["asset"]["name"], "Updated Far Asset")
        
        # 6. Delete both assets
        for aid in list(self.test_asset_ids):
            delete_response = self.client.post(f'/api/v1/admin/delete-asset/{aid}')
            self.assertEqual(delete_response.status_code, 200)
            del_data = json.loads(delete_response.data)
            self.assertTrue(del_data.get("success"))
            self.test_asset_ids.remove(aid)

    def test_duplicate_check_and_override(self):
        # 1. Add a base asset at a specific location
        payload_base = {
            "asset_name": "Base Healthcare Asset",
            "asset_type": "healthcare",
            "sub_type": "Clinic",
            "state": "Lagos",
            "lga": "Alimosho",
            "lat": "6.5600",
            "lon": "3.3100",
            "override_duplicate_check": True,
            "override_lga_check": True
        }
        response = self.client.post('/api/v1/admin/add-asset', 
                                    data=json.dumps(payload_base),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        base_id = data["asset"]["id"]
        self.test_asset_ids.append(base_id)

        # 2. Add another asset at the exact same location (should trigger duplicate warning)
        payload_dup = {
            "asset_name": "Duplicate Healthcare Asset",
            "asset_type": "healthcare",
            "sub_type": "Clinic",
            "state": "Lagos",
            "lga": "Alimosho",
            "lat": "6.5600",
            "lon": "3.3100"
        }
        response = self.client.post('/api/v1/admin/add-asset', 
                                    data=json.dumps(payload_dup),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data.get("duplicate_warning"))
        self.assertIn("distance_m", data)
        self.assertLessEqual(data["distance_m"], 5.0)

        # 3. Add same duplicate asset with override
        payload_dup_override = payload_dup.copy()
        payload_dup_override["override_duplicate_check"] = True
        payload_dup_override["override_lga_check"] = True
        
        response = self.client.post('/api/v1/admin/add-asset', 
                                    data=json.dumps(payload_dup_override),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        dup_id = data["asset"]["id"]
        self.test_asset_ids.append(dup_id)

        # 4. Clean up
        for aid in [base_id, dup_id]:
            if aid in self.test_asset_ids:
                delete_response = self.client.post(f'/api/v1/admin/delete-asset/{aid}')
                self.assertEqual(delete_response.status_code, 200)
                self.test_asset_ids.remove(aid)

    def test_assets_pagination(self):
        # 1. Insert 12 dummy manual assets
        conn = get_db_connection()
        self.assertIsNotNone(conn)
        try:
            with conn.cursor() as cursor:
                for i in range(12):
                    cursor.execute("""
                        INSERT INTO infrastructure_assets (source, asset_name, asset_type, sub_type, state, lga, geom)
                        VALUES ('Admin Portal', %s, 'healthcare', 'Clinic', 'Lagos', 'Alimosho', ST_SetSRID(ST_MakePoint(3.3029, 6.5699), 4326))
                        RETURNING id;
                    """, (f"Pagination Dummy {i}",))
                    self.test_asset_ids.append(cursor.fetchone()[0])
                conn.commit()
        finally:
            release_db_connection(conn)

        # 2. Query page 1 with limit 5
        response = self.client.get('/api/v1/admin/assets?page=1&limit=5')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data.get("success"))
        self.assertEqual(len(data["assets"]), 5)
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["limit"], 5)
        self.assertGreaterEqual(data["total_count"], 12)
        self.assertEqual(data["total_pages"], (data["total_count"] + 4) // 5)

        # 3. Query page 3 with limit 5
        response = self.client.get('/api/v1/admin/assets?page=3&limit=5')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data.get("success"))
        # Since we added 12, page 3 has 2 items remaining (if total manual assets is exactly 12)
        # It could be more if there are other manual assets in the DB, but it must be between 1 and 5.
        self.assertTrue(1 <= len(data["assets"]) <= 5)
        self.assertEqual(data["page"], 3)

    def test_csv_upload(self):
        import io
        csv_content = (
            "asset_name,asset_type,sub_type,state,lga,latitude,longitude\n"
            "CSV Valid Hospital,healthcare,Clinic,Lagos,Alimosho,6.5699,3.3029\n"
            "CSV Far School,education,Primary School,Lagos,Alimosho,9.0820,7.5333\n"
            "CSV Invalid Boundary,healthcare,Clinic,Lagos,Alimosho,40.0,-74.0\n"
            "CSV Missing Fields,healthcare,Clinic,,Alimosho,6.5699,3.3029\n"
        )

        response = self.client.post('/api/v1/admin/upload-csv',
                                    data={'file': (io.BytesIO(csv_content.encode('utf-8')), 'test_assets.csv')},
                                    content_type='multipart/form-data')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data.get("success"))
        self.assertEqual(data["total_rows"], 4)
        self.assertEqual(data["inserted_rows"], 2)
        self.assertEqual(data["failed_rows"], 2)
        
        # 1 warning (CSV Far School is > 25km away from Lagos Alimosho assets)
        self.assertEqual(len(data["warnings"]), 1)
        self.assertIn("Row 2", data["warnings"][0])
        
        # 2 errors (Row 3 is outside Nigeria, Row 4 misses state field)
        self.assertEqual(len(data["errors"]), 2)
        self.assertIn("outside of Nigeria", data["errors"][0])
        self.assertIn("Missing required fields", data["errors"][1])

        # Track the inserted CSV assets for tearDown cleanup
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id FROM infrastructure_assets WHERE asset_name IN ('CSV Valid Hospital', 'CSV Far School') AND source = 'Admin Portal';")
                    for row in cursor.fetchall():
                        self.test_asset_ids.append(row[0])
            finally:
                release_db_connection(conn)

if __name__ == '__main__':
    unittest.main()
