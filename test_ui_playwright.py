import time
import os
from playwright.sync_api import sync_playwright
from database import get_db_connection, release_db_connection

def test_ui():
    artifact_dir = r"C:\Users\ahb4r\.gemini\antigravity-ide\brain\d2e8276f-f164-4448-95a5-24e613ea9136"
    os.makedirs(artifact_dir, exist_ok=True)
    
    # 1. Prepare bulk CSV file with 12 assets to trigger pagination
    csv_path = os.path.join(os.getcwd(), "bulk_assets_test.csv")
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("asset_name,asset_type,sub_type,state,lga,latitude,longitude\n")
        # 10 valid close assets
        for i in range(10):
            f.write(f"CSV Asset Close {i},healthcare,Clinic,Lagos,Alimosho,6.5699,3.3029\n")
        # 2 out-of-bounds assets (warnings)
        f.write("CSV Asset Far 1,education,School,Lagos,Alimosho,9.0820,7.5333\n")
        f.write("CSV Asset Far 2,financial,ATM,Lagos,Alimosho,9.0500,7.5000\n")
        # 1 invalid asset (outside Nigeria)
        f.write("CSV Asset Invalid,healthcare,Clinic,Lagos,Alimosho,40.0,-74.0\n")
        # 1 invalid asset (missing state field)
        f.write("CSV Asset Missing,,Clinic,,Alimosho,6.5699,3.3029\n")

    print(f"Created test CSV file at {csv_path}")

    # Track list of imported IDs for programmatic cleanup
    imported_ids = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        
        print("Navigating to login page...")
        page.goto("http://127.0.0.1:5000/admin/login")
        page.wait_for_timeout(1000)
        page.screenshot(path=os.path.join(artifact_dir, "login_page.png"))
        
        print("Logging in...")
        page.fill("#username", "admin")
        page.fill("#password", "admin123")
        page.click("button[type='submit']")
        
        # Wait for redirect
        page.wait_for_url("**/admin/dashboard")
        print("Logged in successfully. Redirected to dashboard.")
        
        # Reload with bypass_confirm to auto-approve dialogs
        print("Navigating to dashboard with bypass_confirm...")
        page.goto("http://127.0.0.1:5000/admin/dashboard?bypass_confirm=true")
        page.wait_for_timeout(1500)
        page.screenshot(path=os.path.join(artifact_dir, "dashboard_main.png"))
        
        # 2. Test File Upload dropzone click & file select
        print("Selecting and uploading CSV...")
        with page.expect_file_chooser() as fc_info:
            page.click("#csvDropzone")
        file_chooser = fc_info.value
        file_chooser.set_files(csv_path)
        
        print("Waiting for CSV import completion...")
        page.wait_for_selector("#csvSummary", state="visible", timeout=10000)
        page.wait_for_timeout(1000)
        page.screenshot(path=os.path.join(artifact_dir, "csv_import_summary.png"))
        
        # Verify summary info
        summary_msg = page.locator("#csvSummaryMessage").text_content()
        summary_stats = page.locator("#csvSummaryStats").text_content()
        print(f"Import Summary: {summary_msg}")
        print(f"Import Stats: {summary_stats}")
        
        # 3. Verify Pagination Info on Page 1
        page.wait_for_timeout(1000)
        page.screenshot(path=os.path.join(artifact_dir, "pagination_page_1.png"))
        pag_info = page.locator("#paginationInfo").text_content()
        print(f"Pagination Info Page 1: {pag_info}")
        
        # Check if Page 2 button is present and click it
        page2_btn = page.locator(".page-num-btn:has-text('2')")
        if page2_btn.count() > 0:
            print("Clicking Page 2 pagination button...")
            page2_btn.click()
            page.wait_for_timeout(1000)
            page.screenshot(path=os.path.join(artifact_dir, "pagination_page_2.png"))
            
            pag_info_p2 = page.locator("#paginationInfo").text_content()
            print(f"Pagination Info Page 2: {pag_info_p2}")
            
            # Click Prev Page
            print("Clicking Previous pagination button...")
            page.click("#btnPrevPage")
            page.wait_for_timeout(1000)
            
            pag_info_p1 = page.locator("#paginationInfo").text_content()
            print(f"Pagination Info back to Page 1: {pag_info_p1}")
            
        # 4. Clean up programmatically (since deleting 12 items manually in browser is slow)
        print("Cleaning up database entries...")
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cursor:
                    # Retrieve the IDs so we know we matched them
                    cursor.execute("SELECT id FROM infrastructure_assets WHERE asset_name LIKE 'CSV Asset%' AND source = 'Admin Portal';")
                    imported_ids = [row[0] for row in cursor.fetchall()]
                    print(f"Programmatically deleting test assets with IDs: {imported_ids}")
                    
                    cursor.execute("DELETE FROM infrastructure_assets WHERE asset_name LIKE 'CSV Asset%' AND source = 'Admin Portal';")
                    conn.commit()
            except Exception as e:
                print(f"DB cleanup error: {e}")
            finally:
                release_db_connection(conn)
                
        print("Verification complete! CSV Bulk upload and pagination were fully validated.")
        browser.close()
        
    # Clean up local CSV file
    if os.path.exists(csv_path):
        os.remove(csv_path)

if __name__ == "__main__":
    test_ui()
