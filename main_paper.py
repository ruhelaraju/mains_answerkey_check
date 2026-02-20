from flask import Blueprint, request, render_template_string
import sqlite3, requests
from bs4 import BeautifulSoup
import json

main_bp = Blueprint('main_bp', __name__)

def init_db():
    conn = sqlite3.connect('ssc_data.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS results 
                      (roll_no TEXT PRIMARY KEY, name TEXT, score REAL, 
                       category TEXT, shift TEXT, exam_date TEXT, venue TEXT, comp_score REAL)''')
    conn.commit()
    conn.close()

# (HTML Templates stay the same as your provided code)
LEADERBOARD_PAGE = '''...'''
HTML_PAGE = '''...'''

@main_bp.route('/', methods=['GET', 'POST'])
def main_home():
    init_db()
    data = None
    if request.method == 'POST':
        url, cat = request.form.get('url'), request.form.get('category')
        comp_t = 18 if cat=="UR" else (15 if cat in ["OBC","EWS"] else 12)
        cpt_t = 27 if cat=="UR" else (24 if cat in ["OBC","EWS"] else 21)
        try:
            res = requests.get(url)
            soup = BeautifulSoup(res.text, 'html.parser')
            info_tds = soup.find_all('td')
            info = {info_tds[i].text.strip(): info_tds[i+1].text.strip() for i in range(len(info_tds)-1) if info_tds[i].text.strip() in ["Roll Number", "Candidate Name", "Exam Time", "Exam Date", "Test Center Name"]}
            
            qs = soup.find_all(class_='question-pnl')
            subs = {f"Subject {i+1}": {"c":0,"w":0,"l":0,"m":0} for i in range(4)}
            subs["Computer"] = {"c":0,"w":0,"l":0,"m":0}
            merit, comp = 0, 0

            for i, q in enumerate(qs):
                sub = "Subject 1" if i<30 else ("Subject 2" if i<60 else ("Subject 3" if i<105 else ("Subject 4" if i<130 else "Computer")))
                ans_el = q.find(class_='rightAns')
                if not ans_el: continue
                right = ans_el.text[0]
                tds = q.find_all('td')
                chosen = "--"
                for j, r in enumerate(tds):
                    if "Chosen Option" in r.text: chosen = tds[j+1].text.strip()
                pt = 3 if chosen == right else (-1 if chosen != "--" else 0)
                subs[sub]['c' if pt==3 else ('w' if pt==-1 else 'l')] += 1
                subs[sub]['m'] += pt
                if sub != "Computer": merit += pt
                else: comp += pt

            # --- GOOGLE SHEETS LOGIC (Correctly Indented) ---
            gsheet_url = "https://script.google.com/macros/s/AKfycbxHAy5mclNXo98XISQIywbStTBybV3jucAu_Vd_SQp0QQsAaCbvsqk-RR0oWlHhD1tH/exec"
            payload = {
                "roll": info.get("Roll Number"),
                "name": info.get("Candidate Name"),
                "score": merit,
                "category": cat,
                "shift": info.get("Exam Time"),
                "paper_type": "Main"
            }
            try:
                requests.post(gsheet_url, data=json.dumps(payload))
            except:
                pass

            # --- DATABASE LOGIC (Correctly Indented) ---
            conn = sqlite3.connect('ssc_data.db')
            cur = conn.cursor()
            cur.execute("INSERT OR REPLACE INTO results VALUES (?,?,?,?,?,?,?,?)", 
                       (info.get("Roll Number"), info.get("Candidate Name"), merit, cat, info.get("Exam Time"), info.get("Exam Date"), info.get("Test Center Name"), comp))
            conn.commit()

            def get_stats(query, params):
                cur.execute(query, params)
                r = cur.fetchone()[0] + 1
                base_q = query.replace("score > ?", "1").replace("comp_score >= ?", "1").split("WHERE")[0]
                if "category" in query: base_q += " WHERE category = ?"
                elif "shift" in query: base_q += " WHERE shift = ?"
                cur.execute(base_q, (params[1],) if len(params)>1 else ())
                t = cur.fetchone()[0]
                p = round(((t - r) / (t - 1) * 100), 2) if t > 1 else 100.0
                return r, t, p

            ranks, totals, perc = {}, {}, {}
            ranks['overall'], totals['overall'], perc['overall'] = get_stats("SELECT COUNT(*) FROM results WHERE score > ?", (merit,))
            ranks['cat'], totals['cat'], perc['cat'] = get_stats("SELECT COUNT(*) FROM results WHERE score > ? AND category = ?", (merit, cat))
            ranks['shift'], totals['shift'], perc['shift'] = get_stats("SELECT COUNT(*) FROM results WHERE score > ? AND shift = ?", (merit, info.get("Exam Time")))
            cur.execute("SELECT COUNT(*) FROM results WHERE score > ? AND comp_score >= ?", (merit, comp_t))
            ranks['comp'] = cur.fetchone()[0] + 1
            cur.execute("SELECT COUNT(*) FROM results WHERE score > ? AND comp_score >= ?", (merit, cpt_t))
            ranks['cpt'] = cur.fetchone()[0] + 1
            conn.close()
            data = {'name': info.get("Candidate Name"), 'shift': info.get("Exam Time"), 'subs': subs, 'score': merit, 'ranks': ranks, 'totals': totals, 'perc': perc, 'is_comp': comp >= comp_t, 'is_cpt': comp >= cpt_t}
        except Exception as e: 
            print("Error:", e)
    return render_template_string(HTML_PAGE, d=data)

@main_bp.route('/leaderboard')
def leaderboard():
    conn = sqlite3.connect('ssc_data.db')
    cur = conn.cursor()
    cur.execute("SELECT name, score, category, shift FROM results ORDER BY score DESC LIMIT 10")
    players = cur.fetchall()
    conn.close()
    return render_template_string(LEADERBOARD_PAGE, players=players)
