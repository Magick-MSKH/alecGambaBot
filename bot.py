import database

# Initialize database
database.init_db()

print("--- REFUND TEST SETUP ---")
# Reset Alec's points to 1000 for a clean test environment
conn = database.sqlite3.connect(database.DB_NAME)
conn.cursor().execute("UPDATE users SET points = 1000 WHERE username = 'alec'")
conn.commit()
conn.close()

print(f"Alec's Starting Balance: {database.get_balance('alec')}") # Should be 1000

# 1. Alec places a heavy bet
success, message = database.place_bet("alec", 500, "yes")
print(message)
print(f"Alec's Balance after placing bet: {database.get_balance('alec')}") # Should be 500

print("\n--- TRIGGERING CANCELLATION ---")
# 2. Call our new refund function
count, refund_msg = database.cancel_and_refund_bets()
print(refund_msg)

# 3. Verify the points returned safely
print(f"Alec's Balance after refund: {database.get_balance('alec')}") # Should be back to 1000
