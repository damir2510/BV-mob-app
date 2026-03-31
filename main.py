import mysql.connector
from flask import Flask, request, jsonify
from datetime import datetime
import os
from geopy.geocoders import Nominatim

app = Flask(__name__)
geolocator = Nominatim(user_agent="bvapp_locator")

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv('AIVEN_HOST'),
        user=os.getenv('AIVEN_USER'),
        password=os.getenv('AIVEN_PASSWORD'),
        port=os.getenv('AIVEN_PORT'),
        database="defaultdb"
    )

# --- 1. LOGIN ---
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
        if user and user['aktivan'] == 1:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("UPDATE zaposleni SET device_model = %s, last_seen = %s WHERE id = %s", (device, now, user['id']))
            conn.commit()
            return jsonify({"status": "success", "user_id": int(user['id']), "ime": str(user['ime_prezime'])}), 200
        return jsonify({"status": "error", "message": "Neispravni podaci"}), 401
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if conn: conn.close()

# --- 2. PROVERA BAR-KODA (Dohvatanje podataka o aparatu) ---
@app.route('/proveri-aparat', methods=['POST'])
def proveri_aparat():
    data = request.json
    skenirani_kod = data.get('bar_kod')
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        # Koristimo tvoja imena kolona iz tabele 'oprema'
        query = """SELECT vrsta_opreme, proizvodjac, naziv_proizvodjac, seriski_broj, 
                   trenutni_radnik, datum_bazdarenja, vazi_do, bar_kod 
                   FROM oprema WHERE bar_kod = %s"""
        cursor.execute(query, (skenirani_kod,))
        aparat = cursor.fetchone()
        if aparat:
            return jsonify(aparat), 200
        return jsonify({"status": "error", "message": "Aparat nije u bazi"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if conn: conn.close()

# --- 3. AŽURIRANJE (Dugme Azuriraj) ---
@app.route('/azuriraj-lokaciju', methods=['POST'])
def azuriraj_lokaciju():
    data = request.json
    barkod = data.get('bar_kod')
    radnik_ime = data.get('ime_prezime')
    lat = data.get('lat')
    long = data.get('long')
    vreme_sada = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Izračunavanje naziva mesta iz GPS koordinata
    mesto_naziv = "Nepoznata lokacija"
    try:
        location = geolocator.reverse(f"{lat}, {long}")
        if location:
            address = location.raw.get('address', {})
            mesto_naziv = address.get('city') or address.get('town') or address.get('village') or "Teren"
    except:
        pass

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Ažuriramo kolone: trenutni_radnik, datum_kontrole, gps_koordinate, zadnja_lokacija
        query = """UPDATE oprema SET trenutni_radnik = %s, datum_kontrole = %s, 
                   gps_koordinate = %s, zadnja_lokacija = %s WHERE bar_kod = %s"""
        gps_string = f"{lat}, {long}"
        cursor.execute(query, (radnik_ime, vreme_sada, gps_string, mesto_naziv, barkod))
        conn.commit()
        return jsonify({"status": "success", "mesto": mesto_naziv}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if conn: conn.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
