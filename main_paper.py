from flask import Blueprint, request, render_template_string
import sqlite3, requests
from bs4 import BeautifulSoup
import json
import re  # Added for better pattern matching

main_bp = Blueprint('main_bp', __name__)

def init_db():
    conn = sqlite3.connect('ssc_data.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS results 
                      (roll_no TEXT PRIMARY KEY, name TEXT, score REAL, 
                       category TEXT, shift TEXT, exam_date TEXT, venue TEXT, comp_score REAL)''')
    conn.commit()
    conn.close()

# Templates remain as you provided...
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
            
            # 1. Improved Info Extraction
            info_tds = soup.find_all('td')
            info = {}
            for i in range(len(info_tds)-1):
                key = info_tds[i].text.strip()
                val = info_tds[i+1].text.strip()
                if key in ["Roll Number", "Candidate Name", "Exam Time", "Exam Date", "Test Center Name"]:
                    info[key] = val

            # 2. Universal Scraper Logic (Fixes the 0-score issue)
            qs = soup.find_all('div', class_='question-pnl') or soup.find_all('table', class_='question-pnl')
            subs = {f"Subject {i+1}": {"c":0,"w":0,"l":0,"m":0} for i in range(4)}
            subs["Computer"] = {"c":0,"w":0,"l":0,"m":0}
            merit, comp = 0, 0

            for i, q in enumerate(qs):
                sub = "Subject 1" if i<30 else ("Subject 2" if i<60 else ("Subject 3" if i<105 else ("Subject 4" if i<130 else "Computer")))
                
                # Check for both 'rightAns' and 'rightans' (case-insensitive)
                ans_el = q.find(class_=re.compile('rightAns', re.I))
                if not ans_el: continue
                
                right = ans_el.text.strip()[0]
                tds = q.find_all('td')
                chosen = "--"
                
                for j, r in enumerate(tds):
                    txt = r.text.strip()
                    # Works for both English (Chosen Option) and Hindi (चयनित विकल्प)
                    if "Chosen Option" in txt or "चयनित विकल्प" in txt:
                        chosen = tds[j+1].text.strip()
                
                pt = 3 if chosen == right else (-1 if (chosen != "--" and chosen != "None") else 0)
                
                subs[sub]['c' if pt==3 else ('w' if pt==-1 else 'l')] += 1
                subs[sub]['m'] += pt
                if sub != "Computer": merit += pt
                else: comp += pt

            # 3. External Logging & Database
            gsheet_url = "https://script.google.com/macros/s/AKfycbxHAy5mclNXo98XISQIywbStTBybV3jucAu_Vd_SQp0QQsAaCbvsqk-RR0oWlHhD1tH/exec"
            payload = {"roll": info.get("Roll Number"), "name": info.get("Candidate Name"), "score": merit, "category": cat, "shift": info.get("Exam Time"), "paper_type": "Main"}
            
            try: requests.post(gsheet_url, data=json.dumps(payload), timeout=5)
            except: pass

            conn = sqlite3.connect('ssc_data.db')
            cur = conn.cursor()
            cur.execute("INSERT OR REPLACE INTO results VALUES (?,?,?,?,?,?,?,?)", 
                       (info.get("Roll Number", "N/A"), info.get("Candidate Name", "Unknown"), merit, cat, info.get("Exam Time", "N/A"), info.get("Exam Date", "N/A"), info.get("Test Center Name", "N/A"), comp))
            conn.commit()

            # Rank Logic Helper
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
            ranks['shift'], totals['shift'], perc['shift'] = get_stats("SELECT COUNT(*) FROM results WHERE score > ? AND shift = ?", (merit, info.get("Exam Time", "")))
            
            cur.execute("SELECT COUNT(*) FROM results WHERE score > ? AND comp_score >= ?", (merit, comp_t))
            ranks['comp'] = cur.fetchone()[0] + 1
            cur.execute("SELECT COUNT(*) FROM results WHERE score > ? AND comp_score >= ?", (merit, cpt_t))
            ranks['cpt'] = cur.fetchone()[0] + 1
            
            conn.close()
            data = {'name': info.get("Candidate Name"), 'shift': info.get("Exam Time"), 'subs': subs, 'score': merit, 'ranks': ranks, 'totals': totals, 'perc': perc, 'is_comp': comp >= comp_t, 'is_cpt': comp >= cpt_t}
        
        except Exception as e:
            print(f"Deployment Error: {e}")
            
    return render_template_string(HTML_PAGE, d=data)
