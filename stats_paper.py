from flask import Blueprint, request, render_template_string
import sqlite3, requests
from bs4 import BeautifulSoup
import json

stats_bp = Blueprint('stats_bp', __name__)

# Database initialization for Statistics
def init_stats_db():
    conn = sqlite3.connect('ssc_data.db')
    cursor = conn.cursor()
    # Using a separate table for Statistics to avoid mixing ranks with Main Paper
    cursor.execute('''CREATE TABLE IF NOT EXISTS stats_results 
                      (roll_no TEXT PRIMARY KEY, name TEXT, score REAL, 
                       category TEXT, shift TEXT)''')
    conn.commit()
    conn.close()

HTML_PAGE_STATS = '''
<!DOCTYPE html>
<html>
<head>
    <title>Statistics Rank Checker</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #f0f2f5; padding: 20px; }
        .container { max-width: 900px; margin: auto; background: white; padding: 25px; border-radius: 15px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }
        .stats-box { background: #28a745; color: white; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 20px; }
        .rank-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }
        .rank-card { background: #f8f9fa; padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #dee2e6; }
        .btn { padding: 12px 20px; border: none; border-radius: 5px; cursor: pointer; color: white; background: #007bff; text-decoration: none; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { border: 1px solid #eee; padding: 12px; text-align: left; }
    </style>
</head>
<body>
    <div class="container">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <h2>Paper-II: Statistics (200 Marks)</h2>
            <a href="/stats/leaderboard" style="font-weight:bold; color:#28a745; text-decoration:none;">🏆 Stats Leaderboard</a>
        </div>
        <a href="/" style="color: #6c757d; text-decoration: none;">← Back to Hub</a>
        
        <form method="POST" style="margin-top:20px;">
            <input type="text" name="url" placeholder="Paste Statistics Answer Key Link" style="width:60%; padding:12px;" required>
            <select name="category" style="padding:12px;">
                <option value="UR">UR</option><option value="OBC">OBC</option>
                <option value="EWS">EWS</option><option value="SC">SC</option><option value="ST">ST</option>
            </select>
            <button type="submit" class="btn">Check Rank</button>
        </form>

        {% if d %}
        <div style="margin-top:20px;">
            <div class="stats-box">
                <h3>Candidate: {{ d.name }}</h3>
                <h1>{{ d.score }} / 200</h1>
            </div>

            <div class="rank-grid">
                <div class="rank-card"><h3>Overall Rank</h3><h2>{{ d.ranks.overall }} / {{ d.totals.overall }}</h2></div>
                <div class="rank-card"><h3>Category Rank</h3><h2>{{ d.ranks.cat }} / {{ d.totals.cat }}</h2></div>
            </div>

            <table>
                <tr><th>Correct (+2)</th><td>{{ d.summary.c }}</td></tr>
                <tr><th>Wrong (-0.5)</th><td>{{ d.summary.w }}</td></tr>
                <tr><th>Final Score</th><td><b>{{ d.score }}</b></td></tr>
            </table>
        </div>
        {% endif %}
    </div>
</body>
</html>
'''

@stats_bp.route('/', methods=['GET', 'POST'])
def stats_home():
    init_stats_db()
    data = None
    if request.method == 'POST':
        url, cat = request.form.get('url'), request.form.get('category')
        try:
            res = requests.get(url)
            soup = BeautifulSoup(res.text, 'html.parser')
            info_tds = soup.find_all('td')
            info = {info_tds[i].text.strip(): info_tds[i+1].text.strip() for i in range(len(info_tds)-1) if info_tds[i].text.strip() in ["Roll Number", "Candidate Name", "Exam Time"]}
            
            qs = soup.find_all(class_='question-pnl')
            correct, wrong = 0, 0

            for q in qs[:100]: # Processing only 100 questions for Stats paper
                ans_el = q.find(class_='rightAns')
                if not ans_el: continue
                right = ans_el.text[0]
                tds = q.find_all('td')
                chosen = "--"
                for j, r in enumerate(tds):
                    if "Chosen Option" in r.text: chosen = tds[j+1].text.strip()
                if chosen == right: correct += 1
                elif chosen != "--": wrong += 1

            merit = (correct * 2) - (wrong * 0.5)
            gsheet_url = "https://script.google.com/macros/s/AKfycbxHAy5mclNXo98XISQIywbStTBybV3jucAu_Vd_SQp0QQsAaCbvsqk-RR0oWlHhD1tH/exec"
            payload = {
                "roll": info.get("Roll Number"),
                "name": info.get("Candidate Name"),
                "score": merit,
                "category": cat,
                "shift": info.get("Exam Time"),
                "paper_type": "Stats"
            }
            try:
                requests.post(gsheet_url, data=json.dumps(payload))
            except:
                pass
            
            conn = sqlite3.connect('ssc_data.db')
            cur = conn.cursor()
            cur.execute("INSERT OR REPLACE INTO stats_results VALUES (?,?,?,?,?)", 
                       (info.get("Roll Number"), info.get("Candidate Name"), merit, cat, info.get("Exam Time")))
            conn.commit()

            # Rank Logic
            def get_stats_rank(query, params):
                cur.execute(query, params)
                r = cur.fetchone()[0] + 1
                base_q = query.replace("score > ?", "1").split("WHERE")[0]
                if "category" in query: base_q += " WHERE category = ?"
                cur.execute(base_q, (params[1],) if len(params)>1 else ())
                t = cur.fetchone()[0]
                return r, t

            ranks, totals = {}, {}
            ranks['overall'], totals['overall'] = get_stats_rank("SELECT COUNT(*) FROM stats_results WHERE score > ?", (merit,))
            ranks['cat'], totals['cat'] = get_stats_rank("SELECT COUNT(*) FROM stats_results WHERE score > ? AND category = ?", (merit, cat))
            
            conn.close()
            data = {'name': info.get("Candidate Name"), 'score': merit, 'summary': {'c':correct, 'w':wrong}, 'ranks': ranks, 'totals': totals}
        except Exception as e: print("Error:", e)
    return render_template_string(HTML_PAGE_STATS, d=data)

@stats_bp.route('/leaderboard')
def leaderboard():
    conn = sqlite3.connect('ssc_data.db')
    cur = conn.cursor()
    cur.execute("SELECT name, score, category, shift FROM stats_results ORDER BY score DESC LIMIT 10")
    players = cur.fetchall()
    conn.close()

    return f"<h1>Stats Top 10</h1><ul>" + "".join([f"<li>{p[0]} - {p[1]} ({p[2]})</li>" for p in players]) + "</ul><a href='/stats/'>Back</a>"
