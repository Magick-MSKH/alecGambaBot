import sqlite3
import gspread
import database

# Cache GLOBAL ref for login session
GC_SESSION = None

def sync_to_google_sheets():
    """ Read from local SQLite database, overwrite Data tab.
        Handle token expirations and empty database states gracefully without crashing! :O
    """

    global GC_SESSION
    
    try:
        # Check if we need to log in fresh OR refresh an expired token!!
        if GC_SESSION is None:
            GC_SESSION = gspread.service_account(filename="sheets_credentials.json")
        else:
            try:
                # Force gspread to check if the 1h token needs a refresh
                GC_SESSION.auth.refresh(gspread.auth.requests.Requests())
            except Exception:
                # If refreshing fails, log in from scratch to restore the link
                GC_SESSION = gspread.service_account(filename="sheets_credentials.json")
        
        # Open the workbook using our newly validated login session
        sh = GC_SESSION.open("Alec Stream Gamba Leaderboard")
        worksheet = sh.worksheet("Data") # Sets the Data tab/sheet as the entry point

        # Pull data from SQLite
        conn = sqlite3.connect(database.DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT username, points FROM users ORDER BY points DESC")
        rows = cursor.fetchall()
        conn.close()

        sheet_data = [["Rank", "Username", "Current Points", "Total Bets", "Wins", "Losses", "All-Time Peak"]]

        if not rows:
            sheet_data.append(["#0", "No players registered yet!", 0, 0, 0, 0, 0])
            worksheet.clear()
            worksheet.update('A1', sheet_data)
            print("📊 Data tab cleared and initialized for a clean slate!")
            return

        for index, (username, points) in enumerate(rows, 1):
            stats = database.get_player_stats(username)
            
            if stats is None:
                placed, won, lost, peak = 0, 0, 0, points
            else:
                _, placed, won, lost, peak = stats
                
            sheet_data.append([f"#{index}", username, points, placed, won, lost, peak])
            
        worksheet.clear()
        worksheet.update('A1', sheet_data)
        print("📊 Data tab successfully updated!")
    
    except Exception as e:
        # If the token fails or if GSpread locks up or drops, print a debug message
        # Bypass the crash handler and restart the script
        print(f"🐞 [DEBUG] GSpread Failure! Restart on next tic: {e}")