import mysql.connector
from flask import Flask, request, jsonify
from datetime import datetime
import os

app = Flask(__name__)

# Podaci za Aiven (podesi ih na Railway-u kao Environment Variables)
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv('AIVEN_HOST'),
        user=os.getenv('AIVEN_USER'),
        password=os.getenv('AIVEN_PASSWORD'),
        port=os.getenv('AIVEN_PORT'),
        database="defaultdb"
    )

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('korisnicko_ime')
    password = data.get('lozinka')
    device = data.get('device_model')

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Provera korisnika
        query = "SELECT id, ime_prezime, aktivan FROM zaposleni WHERE korisnicko_ime = %s AND Lozinka = %s"
        cursor.execute(query, (username, password))
        user = cursor.fetchone()

        if user:
            if user['aktivan'] == 1:
                # Update modela telefona i zadnjeg viđenja
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                update_query = "UPDATE zaposleni SET device_model = %s, last_seen = %s WHERE id = %s"
                cursor.execute(update_query, (device, now, user['id']))
                conn.commit()
                
                return jsonify({
                    "status": "success", 
                    "user_id": int(user['id']),  # Osiguravamo da je broj
                    "ime": str(user['ime_prezime']) # Osiguravamo da je tekst (String)
                }), 200
            else:
                return jsonify({"status": "error", "message": "Korisnik nije aktivan"}), 403
        
        return jsonify({"status": "error", "message": "Pogrešni podaci"}), 401

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if 'conn' in locals(): conn.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
