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
    print(f"STIGLO SA TELEFONA: User: {data.get('korisnicko_ime')}, Pass: {data.get('lozinka')}")
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

# --- 2. PROVERA I AUTOMATSKO AŽURIRANJE LOKACIJE ---
@app.route('/proveri-aparat', methods=['POST'])
def proveri_aparat():
    data = request.json
    skenirani_kod = data.get('bar_kod')
    radnik_ime = data.get('ime_prezime')
    lat = data.get('lat')
    long = data.get('long')
    vreme_sada = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Ako imamo koordinate, prvo ažuriramo lokaciju u bazi
        if lat and long and lat != 0:
            mesto_naziv = "Teren"
            try:
                location = geolocator.reverse(f"{lat}, {long}")
                if location:
                    address = location.raw.get('address', {})
                    mesto_naziv = address.get('city') or address.get('town') or address.get('village') or "Teren"
            except:
                pass
            
            gps_string = f"{lat}, {long}"
            update_query = """UPDATE oprema SET trenutni_radnik = %s, datum_kontrole = %s, 
                             gps_koordinate = %s, zadnja_lokacija = %s WHERE bar_kod = %s"""
            cursor.execute(update_query, (radnik_ime, vreme_sada, gps_string, mesto_naziv, skenirani_kod))
            conn.commit()

        # 2. Zatim izvlačimo podatke o aparatu da ih prikažemo na ekranu
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
