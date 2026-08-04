import sqlite3
import gspread
import database

GC_SESSION = None

def sync_to_google_sheets():
    global GC_SESSION
    
    try:
        if GC_SESSION is None:
            GC_SESSION = gspread.service_account(filename="sheets_credentials.json")
        else:
            try:
                GC_SESSION.auth.refresh(gspread.auth.requests.Requests())
            except Exception:
                GC_SESSION = gspread.service_account(filename="sheets_credentials.json")
        
        sh = GC_SESSION.open("Alec Stream Gamba Leaderboard")
        worksheet = sh.worksheet("Data")

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
        print(f"🐞 [DEBUG] GSpread Failure! Restart on next tic: {e}")