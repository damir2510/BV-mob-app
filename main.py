import mysql.connector
from flask import Flask, request, jsonify
from datetime import datetime
import os

app = Flask(__name__)

# Funkcija za konekciju na Aiven SQL (koristi Environment Variables sa Railway-a)
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv('AIVEN_HOST'),
        user=os.getenv('AIVEN_USER'),
        password=os.getenv('AIVEN_PASSWORD'),
        port=os.getenv('AIVEN_PORT'),
        database="defaultdb"
    )

# --- 1. RUTA ZA LOGOVANJE ---
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('korisnicko_ime')
    password = data.get('lozinka')
    device = data.get('device_model')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = "SELECT id, ime_prezime, aktivan FROM zaposleni WHERE korisnicko_ime = %s AND Lozinka = %s"
        cursor.execute(query, (username, password))
        user = cursor.fetchone()

        if user:
            if user['aktivan'] == 1:
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                update_query = "UPDATE zaposleni SET device_model = %s, last_seen = %s WHERE id = %s"
                cursor.execute(update_query, (device, now, user['id']))
                conn.commit()
                
                return jsonify({
                    "status": "success", 
                    "user_id": int(user['id']), 
                    "ime": str(user['ime_prezime'])
                }), 200
            else:
                return jsonify({"status": "error", "message": "Korisnik nije aktivan"}), 403
        
        return jsonify({"status": "error", "message": "Pogrešni podaci"}), 401
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if conn: conn.close()

# --- 2. RUTA ZA PROVERU APARATA (Čim se skenira bar-kod) ---
@app.route('/proveri-aparat', methods=['POST'])
def proveri_aparat():
    data = request.json
    barkod = data.get('bar_kod')
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Upit koji vuče svih 8 polja koja si tražio
        query = """SELECT proizvodjac, model, inv_broj, serijski_broj, 
                   zaduzen_na, vazi_do, mesto, datum 
                   FROM oprema WHERE inv_broj = %s OR serijski_broj = %s"""
        # Proveravamo i po inventarskom i po serijskom (šta god da je u bar-kodu)
        cursor.execute(query, (barkod, barkod))
        aparat = cursor.fetchone()
        
        if aparat:
            return jsonify(aparat), 200
        else:
            return jsonify({"status": "error", "message": "Aparat nije u bazi"}), 404
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if conn: conn.close()

# --- 3. RUTA ZA AŽURIRANJE (Dugme Azuriraj) ---
@app.route('/azuriraj-lokaciju', methods=['POST'])
def azuriraj_lokaciju():
    data = request.json
    inv_broj = data.get('inv_broj')
    radnik_ime = data.get('ime_prezime') # Ime radnika koji je ulogovan
    gps = data.get('gps_koordinate') # Stiže kao "lat, long"
    vreme_sada = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Ažuriramo bazu sa novom lokacijom i ko je zadnji skenirao
        query = "UPDATE oprema SET zaduzen_na = %s, datum = %s, mesto = %s WHERE inv_broj = %s"
        cursor.execute(query, (radnik_ime, vreme_sada, gps, inv_broj))
        conn.commit()
        
        return jsonify({"status": "success", "message": "Podaci su ažurirani u bazi"}), 200
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if conn: conn.close()

if __name__ == '__main__':
    # Railway zahteva da aplikacija sluša na portu iz okruženja
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
