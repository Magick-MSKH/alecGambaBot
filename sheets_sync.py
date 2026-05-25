import sqlite3
import gspread
import database

def sync_to_google_sheets():
    """
    Reads users from the local SQLite database and overwrites the 'Data' tab.
    Leaves the 'Dashboard' tab completely untouched.
    """
    try:
        # 1. Connect to your Google Service Account
        gc = gspread.service_account(filename="sheets_credentials.json")
        
        # 2. Open the workbook by its name
        sh = gc.open("Alec Stream Gamba Leaderboard")
        
        # FIX: Target the specific 'Data' worksheet tab explicitly
        worksheet = sh.worksheet("Data")
        
        # 3. Pull data from SQLite, sorted from richest to poorest
        conn = sqlite3.connect(database.DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT username, points FROM users ORDER BY points DESC")
        rows = cursor.fetchall()
        conn.close()
        
        # 4. Format data with headers
        sheet_data = [["Rank", "Username", "Current Points", "Total Bets", "Wins", "Losses", "All-Time Peak"]]

        if not rows:
            sheet_data.append(["#0", "No players registered yet!", 0, 0, 0, 0, 0])
            worksheet.clear()
            worksheet.update('A1', sheet_data)
            print("📊 Data tab cleared and initialized for a clean slate!")
            return

        for index, (username, points) in enumerate(rows, 1):
            # Fetch stats per row to populate columns D:G
            stats = database.get_player_stats(username)

            if stats is None:
                placed, won, lost, peak = 0, 0, 0, points
            else:
                _, placed, won, lost, peak = stats
            
            sheet_data.append([f"#{index}", username, points, placed, won, lost, peak])
            
        # 5. Clear the old data and write the new list
        worksheet.clear()
        worksheet.update('A1', sheet_data)
        print("📊 Data tab successfully updated!")
        
    except Exception as e:
        print(f"⚠️ Google Sheets Sync Failed: {e}")