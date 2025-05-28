from flask import Flask, request, redirect
import pandas as pd
import sqlite3
from datetime import datetime
import requests

app = Flask(__name__)

# 데이터 로드
data = pd.read_csv('epigen_data.csv')

# Hugging Face Inference API 토큰 (환경변수로 관리 권장, 예시는 하드코딩)
HF_TOKEN = "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"  # 본인 토큰으로 교체

def get_ai_advice(prompt):
    API_URL = "https://api-inference.huggingface.co/models/distilgpt2"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {"inputs": prompt, "options": {"wait_for_model": True}}
    response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
    if response.status_code == 200:
        result = response.json()
        if isinstance(result, list) and "generated_text" in result[0]:
            return result[0]["generated_text"]
        else:
            return str(result)
    else:
        return "AI 서버 오류"

def calculate_risk(user_data):
    total_risk = 0
    alzheimer_risk = 0.1
    cardio_risk = 0.1
    diabetes_risk = 0.1
    count = 0
    for factor, value in user_data.items():
        if factor not in ['age_group', 'date']:
            matching_row = data[(data['Lifestyle_Factor'] == factor) & (data['Value'] == value)]
            if not matching_row.empty:
                total_risk += float(matching_row['Health_Risk_Score'].iloc[0])
                alzheimer_risk = max(alzheimer_risk, float(matching_row['Alzheimer_Risk'].iloc[0]))
                cardio_risk = max(cardio_risk, float(matching_row['Cardiovascular_Risk'].iloc[0]))
                diabetes_risk = max(diabetes_risk, float(matching_row['Diabetes_Risk'].iloc[0]))
                count += 1
    return total_risk / max(1, count), alzheimer_risk, cardio_risk, diabetes_risk

def generate_personalized_advice(risk_score, user_input, age_group):
    base_prompt = f"User has a health risk score of {risk_score} (1-5, higher is worse). They are {'over 60 years old' if age_group == 'over_60' else 'under 60'}. "
    if user_input:
        base_prompt += f"They mentioned: {user_input}. "
    base_prompt += "Provide personalized health advice in a friendly tone to help prevent aging-related diseases."
    return get_ai_advice(base_prompt)

def save_user_data(user_data, risk_score, advice):
    conn = sqlite3.connect('epigenai_users.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, age_group TEXT, sleep TEXT, stress TEXT, diet TEXT, exercise TEXT, risk_score REAL, advice TEXT, date TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    cursor.execute('INSERT INTO users (age_group, sleep, stress, diet, exercise, risk_score, advice, date) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                   (user_data['age_group'], user_data['sleep'], user_data['stress'], user_data['diet'], user_data['exercise'], risk_score, advice, user_data['date']))
    conn.commit()
    conn.close()

def check_user_records():
    conn = sqlite3.connect('epigenai_users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT date FROM users')
    dates = cursor.fetchall()
    conn.close()
    return len(dates) >= 7

def simulate_improvement(user_data, factor, improved_value):
    improved_data = user_data.copy()
    improved_data[factor] = improved_value
    risk, _, _, _ = calculate_risk(improved_data)
    return risk

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        age_group = request.form.get('age_group', 'under_60')
        sleep_hours = request.form.get('sleep', '6')
        stress_level = request.form.get('stress', 'Low')
        diet_quality = request.form.get('diet', 'Good')
        exercise_minutes = request.form.get('exercise', '30')
        date = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))
        user_input = request.form.get('user_comment', '')
        user_data = {
            'age_group': age_group,
            'sleep': sleep_hours,
            'stress': stress_level,
            'diet': diet_quality,
            'exercise': exercise_minutes,
            'date': date
        }
        risk, alzheimer_risk, cardio_risk, diabetes_risk = calculate_risk({
            'age_group': age_group,
            'Sleep_Hours': sleep_hours,
            'Stress_Level': stress_level,
            'Diet_Quality': diet_quality,
            'Exercise_Minutes': exercise_minutes
        })
        advice = generate_personalized_advice(risk, user_input, age_group)
        save_user_data(user_data, risk, advice)
        return redirect('/history')
    return '''
<h1>EpigenAI: 후성유전학 기반 건강습관 분석</h1>
<form method="post">
<label>연령대:</label>
<select name="age_group">
<option value="under_60">60세 미만</option>
<option value="over_60">60세 이상</option>
</select><br><br>
<label>날짜:</label>
<input type="date" name="date" value="{today}" required><br><br>
<label>수면 시간 (시간):</label>
<select name="sleep">
<option value="6">6시간</option>
<option value="8">8시간</option>
</select><br><br>
<label>스트레스 수준:</label>
<select name="stress">
<option value="Low">낮음</option>
<option value="High">높음</option>
</select><br><br>
<label>식단 품질:</label>
<select name="diet">
<option value="Good">좋음</option>
<option value="Poor">나쁨</option>
</select><br><br>
<label>운동 시간 (분):</label>
<select name="exercise">
<option value="30">30분</option>
<option value="0">0분</option>
</select><br><br>
<label>추가 의견 (선택 사항):</label>
<textarea name="user_comment" rows="3" cols="30" placeholder="건강 상태나 궁금한 점을 적어주세요."></textarea><br><br>
<input type="submit" value="데이터 저장">
</form>
'''.replace("{today}", datetime.now().strftime('%Y-%m-%d'))

@app.route('/history')
def history():
    conn = sqlite3.connect('epigenai_users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users ORDER BY timestamp DESC')
    records = cursor.fetchall()
    conn.close()
    html = "<h1>나의 건강 기록</h1><table border='1' style='margin: 0 auto; font-size: 18px;'>"
    html += "<tr><th>날짜</th><th>연령대</th><th>수면</th><th>스트레스</th><th>식단</th><th>운동</th><th>위험도</th><th>AI 조언</th></tr>"
    for record in records:
        html += f"<tr><td>{record[8]}</td><td>{record[1]}</td><td>{record[2]}</td><td>{record[3]}</td><td>{record[4]}</td><td>{record[5]}</td><td>{record[6]}</td><td>{record[7][:40]}...</td></tr>"
    html += "</table><br><a href='/'>홈으로 돌아가기</a>"
    if check_user_records():
        html += "<br><b>7일 이상 기록이 있으니 결과 분석이 가능합니다!</b>"
        html += "<br><a href='/result'>주간 결과 분석 보기</a>"
    else:
        html += "<br><b>7일 이상 기록을 입력해야 결과를 볼 수 있습니다.</b>"
    return html

@app.route('/result')
def result():
    conn = sqlite3.connect('epigenai_users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT risk_score, date FROM users ORDER BY date DESC LIMIT 7')
    records = cursor.fetchall()
    conn.close()
    if len(records) < 7:
        return "<h1>7일 이상 기록이 필요합니다.</h1><a href='/'>홈으로 돌아가기</a>"
    risk_scores = [float(r[0]) for r in records]
    avg_risk = sum(risk_scores) / len(risk_scores)
    trend = "개선됨" if risk_scores[0] < risk_scores[-1] else "악화됨" if risk_scores[0] > risk_scores[-1] else "유사함"
    html = f"<h1>주간 건강 분석 결과</h1><p>평균 위험도: {avg_risk:.2f}</p><p>위험도 추세: {trend}</p>"
    html += "<table border='1' style='margin: 0 auto; font-size: 18px;'><tr><th>날짜</th><th>위험도</th></tr>"
    for r in records:
        html += f"<tr><td>{r[1]}</td><td>{r[0]}</td></tr>"
    html += "</table><br><a href='/'>홈으로 돌아가기</a>"
    return html

@app.route('/education')
def education():
    return '''
<h1>후성유전학 교육 콘텐츠</h1>
<div style="font-size:18px; padding:20px; background:#fff; border-radius:10px; width:80%; margin:0 auto;">
<b>후성유전학이란?</b> 유전자의 DNA 서열이 변하지 않으면서도 생활습관이나 환경이 유전자 발현에 영향을 미치는 과학입니다.<br>
<b>왜 중요한가요?</b> 수면 부족, 스트레스, 잘못된 식습관은 DNA 메틸화를 변화시켜 알츠하이머, 심혈관 질환 같은 노화 질병 위험을 높일 수 있습니다.<br>
<b>어떻게 도움을 줄까요?</b> EpigenAI는 생활습관을 분석하여 이러한 위험을 줄이는 방법을 제안합니다.
</div>
<br><a href='/' >홈으로 돌아가기</a>
'''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
