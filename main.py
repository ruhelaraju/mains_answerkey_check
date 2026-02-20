from flask import Flask, render_template_string
from main_paper import main_bp
from stats_paper import stats_bp
from waitress import serve

app = Flask(__name__)

# Registering the Blueprints with unique URL paths
# Main Paper will be at: yoursite.com/main
# Stats Paper will be at: yoursite.com/stats
app.register_blueprint(main_bp, url_prefix='/main')
app.register_blueprint(stats_bp, url_prefix='/stats')

# The Landing Page HTML
HOME_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>SSC Rank Checker Hub</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f0f2f5; margin: 0; display: flex; align-items: center; justify-content: center; height: 100vh; }
        .hub-card { background: white; padding: 40px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); text-align: center; max-width: 500px; width: 90%; }
        h1 { color: #1c1e21; margin-bottom: 10px; }
        p { color: #606770; margin-bottom: 30px; }
        .btn-container { display: flex; flex-direction: column; gap: 15px; }
        .btn { padding: 20px; border-radius: 12px; text-decoration: none; font-size: 18px; font-weight: bold; color: white; transition: transform 0.2s, box-shadow 0.2s; }
        .btn-main { background: linear-gradient(135deg, #007bff, #0056b3); }
        .btn-stats { background: linear-gradient(135deg, #28a745, #1e7e34); }
        .btn:hover { transform: translateY(-3px); box-shadow: 0 5px 15px rgba(0,0,0,0.2); opacity: 0.9; }
    </style>
</head>
<body>
    <div class="hub-card">
        <h1>SSC Checker Hub</h1>
        <p>Choose the paper you want to analyze:</p>
        <div class="btn-container">
            <a href="/main" class="btn btn-main">Main Paper Checker<br><span style="font-size:12px; font-weight:normal;">(390 Marks Logic)</span></a>
            <a href="/stats" class="btn btn-stats">Statistics Paper Checker<br><span style="font-size:12px; font-weight:normal;">(200 Marks Logic)</span></a>
        </div>
        <div style="margin-top: 25px; font-size: 12px; color: #90949c;">
            Designed for JSO & Statistical Investigator Aspirants
        </div>
    </div>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HOME_HTML)

if __name__ == '__main__':
    print("🚀 Server starting on http://localhost:8080")
    serve(app, host='0.0.0.0', port=8080)