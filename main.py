import os
import json
import sqlite3
import hashlib
import datetime
from typing import Optional
from pathlib import Path

import jwt
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# ─── 配置 ─────────────────────────────────────────────────────────────────────
DB_PATH = "practice.db"
SECRET_KEY = os.getenv("SECRET_KEY", "tesla-sales-secret-2024-change-me")
STATIC_DIR = Path(__file__).parent / "static"

# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(title="Tesla延保销售陪练系统")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── 数据库 ───────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            scenario TEXT NOT NULL,
            standard_answer TEXT NOT NULL,
            key_points TEXT NOT NULL,
            tips TEXT DEFAULT '',
            order_num INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS practice_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            user_answer TEXT NOT NULL,
            score INTEGER NOT NULL,
            feedback TEXT NOT NULL,
            strengths TEXT DEFAULT '[]',
            improvements TEXT DEFAULT '[]',
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (question_id) REFERENCES questions(id)
        );
    """)

    if conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0] == 0:
        _seed_questions(conn)

    admin_hash = hashlib.sha256(b"admin888").hexdigest()
    conn.execute(
        "INSERT OR IGNORE INTO users (username, password_hash, role) VALUES ('admin', ?, 'admin')",
        (admin_hash,)
    )
    conn.commit()
    conn.close()

def _seed_questions(conn):
    questions = [
        (
            "开场白", "首次接触客户", 1,
            "客户刚提完新车，你作为延保顾问主动上前介绍",
            "您好，恭喜您提到您心仪的Tesla！我是延保顾问，想跟您分享一个保护爱车的重要信息。Tesla的新车保修是4年或8万公里，但Model 3和Model Y的电动机、电池等核心部件维修费用非常高，一旦超出保修期，一个小故障就可能花费数万元。我们的延保方案可以将保障期延长至8年，让您未来几年完全无忧驾驶。请问您有几分钟时间了解一下吗？",
            "恭喜提车,保修期4年或8万公里,核心部件维修费高,延保延长至8年,礼貌请求时间",
            "语气要热情但不强硬，给客户选择的空间"
        ),
        (
            "异议处理", "客户说不会坏", 2,
            "客户表示Tesla质量很好，觉得不需要购买延保",
            "您说得对，Tesla的品质确实非常出色！正因为如此，很多车主觉得不会出问题。但根据我们的服务数据，即使是品质最好的车，在第4到8年也会有零部件自然老化的情况，尤其是Tesla的高压电池、电动机控制器这些高科技部件，单个更换费用就在3到8万元不等。延保不是因为车会坏，而是当意外发生时，能让您零成本解决问题。就像买保险一样，买了希望用不到，但有了心里踏实。",
            "认同客户观点,转折引出数据,举例高费用部件,类比保险概念,强调安心价值",
            "先认同后转折，避免直接反驳客户"
        ),
        (
            "异议处理", "客户说太贵了", 3,
            "客户对延保价格表示顾虑，认为延保费用太高",
            "完全理解您对价格的考量！我们来算一笔账：我们的延保方案大约是一万多元，分摊到4年保障期，每天不到10块钱。而Tesla一个充电桩控制器故障就需要1.5万元，电池模组出问题更是3到6万元起。相比之下，延保的投入其实非常划算。而且购买延保后，您的车在保障期内任何故障都直接送官方售后，不用担心被不正规维修店坑，也不用担心二手车卖不出好价格，实际上还帮您保住了车辆的残值。",
            "理解客户顾虑,分摊费用每天不到10元,举例对比维修费用,强调官方保障,提及二手保值",
            "用具体数字说话，让客户感受到价值；先同理后算账"
        ),
        (
            "产品介绍", "介绍延保覆盖范围", 4,
            "客户询问延保具体包含哪些内容，覆盖哪些部件",
            "我们的延保方案覆盖Tesla几乎所有核心机械和电气部件。主要包括四大类：第一是动力系统，包括电动机、减速器、电机控制器，这是Tesla最贵的部件；第二是高压电池系统，除正常容量衰减外的电池故障全部覆盖；第三是车身电气系统，包括中控大屏、车载电脑、各类传感器；第四是驾驶辅助系统，Autopilot相关的硬件故障都在保障范围内。简单说就是，除了刹车片、轮胎、雨刷这类易损耗件，其他主要部件坏了我们都管，而且全部在Tesla官方授权店维修，使用原厂配件，您完全放心。",
            "四大类覆盖范围,动力系统,高压电池,车身电气,驾驶辅助,不覆盖易损件,官方维修原厂配件",
            "分点介绍，条理清晰，重点突出最贵的部件"
        ),
        (
            "促成成交", "临门一脚促成购买", 5,
            "客户已经表示有兴趣但还在犹豫，需要最后推动",
            "您现在购买延保是最合适的时机，我给您说三个原因：第一，新车刚提，所有部件状态最好，延保可以立即生效，没有任何等待期和检测要求；第二，目前我们有提车专属优惠，过了这个窗口期，您需要额外提交车辆检测报告，而且价格会有所调整；第三，您现在刚入手Tesla，正好趁热打铁把后顾之忧一并解决，以后专心享受驾驶乐趣就好了。您是考虑标准版还是尊享版呢？",
            "三个购买理由,新车立即生效无等待,提车专属优惠,趁热打铁,二选一假设成交",
            "用二选一代替是否购买，制造决策感；给出具体理由增加紧迫感"
        ),
    ]
    conn.executemany(
        "INSERT INTO questions (category, title, order_num, scenario, standard_answer, key_points, tips) VALUES (?,?,?,?,?,?,?)",
        questions
    )

# ─── 认证 ─────────────────────────────────────────────────────────────────────
def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def make_token(user_id: int, username: str, role: str) -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def parse_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "登录已过期，请重新登录")
    except Exception:
        raise HTTPException(401, "无效的登录凭证")

async def current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "请先登录")
    return parse_token(authorization[7:])

async def admin_user(user: dict = Depends(current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(403, "需要管理员权限")
    return user

# ─── 请求模型 ─────────────────────────────────────────────────────────────────
class LoginReq(BaseModel):
    username: str
    password: str

class RegisterReq(BaseModel):
    username: str
    password: str

class SubmitReq(BaseModel):
    question_id: int
    user_answer: str

class QuestionReq(BaseModel):
    category: str
    title: str
    scenario: str
    standard_answer: str
    key_points: str
    tips: str = ""
    order_num: int = 0

# ─── 关键词评分 ───────────────────────────────────────────────────────────────
def keyword_score(key_points: str, user_answer: str) -> dict:
    points = [p.strip() for p in key_points.split(",") if p.strip()]
    matched = [p for p in points if p in user_answer]
    missed = [p for p in points if p not in user_answer]
    total = len(points)
    hit = len(matched)
    score = int((hit / max(total, 1)) * 100)

    if score >= 85:
        feedback = f"非常出色！覆盖了{hit}/{total}个关键要点，话术完整专业。"
    elif score >= 70:
        feedback = f"表现良好！覆盖了{hit}/{total}个关键要点，还有小部分可以补充。"
    elif score >= 55:
        feedback = f"基本达标，覆盖了{hit}/{total}个关键要点，建议重点加强遗漏的要点。"
    else:
        feedback = f"需要加强练习，仅覆盖了{hit}/{total}个关键要点，请对照标准答案重新练习。"

    strengths = [f"✓ 提到了「{p}」" for p in matched] or ["暂无匹配要点"]
    improvements = [f"未提及「{p}」，注意补充" for p in missed] or ["所有要点均已覆盖，继续保持！"]

    return {
        "score": score,
        "feedback": feedback,
        "strengths": strengths,
        "improvements": improvements
    }

# ─── 认证接口 ─────────────────────────────────────────────────────────────────
@app.post("/api/register")
def register(req: RegisterReq):
    if len(req.username) < 2:
        raise HTTPException(400, "用户名至少2个字符")
    if len(req.password) < 6:
        raise HTTPException(400, "密码至少6个字符")
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (req.username, hash_pw(req.password))
        )
        conn.commit()
        return {"message": "注册成功"}
    except sqlite3.IntegrityError:
        raise HTTPException(400, "用户名已被使用")
    finally:
        conn.close()

@app.post("/api/login")
def login(req: LoginReq):
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ? AND password_hash = ?",
        (req.username, hash_pw(req.password))
    ).fetchone()
    conn.close()
    if not user:
        raise HTTPException(401, "用户名或密码错误")
    token = make_token(user["id"], user["username"], user["role"])
    return {"token": token, "username": user["username"], "role": user["role"]}

# ─── 题目接口 ─────────────────────────────────────────────────────────────────
@app.get("/api/questions")
def list_questions(user: dict = Depends(current_user)):
    conn = get_db()
    rows = conn.execute(
        "SELECT id, category, title, scenario, key_points, tips, order_num FROM questions ORDER BY order_num"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/questions/{qid}")
def get_question(qid: int, user: dict = Depends(current_user)):
    conn = get_db()
    row = conn.execute("SELECT * FROM questions WHERE id = ?", (qid,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "题目不存在")
    return dict(row)

# ─── 练习接口 ─────────────────────────────────────────────────────────────────
@app.post("/api/practice/submit")
def submit_practice(req: SubmitReq, user: dict = Depends(current_user)):
    if not req.user_answer.strip():
        raise HTTPException(400, "回答不能为空")

    conn = get_db()
    question = conn.execute("SELECT * FROM questions WHERE id = ?", (req.question_id,)).fetchone()
    if not question:
        conn.close()
        raise HTTPException(404, "题目不存在")

    result = keyword_score(question["key_points"], req.user_answer)

    conn.execute(
        """INSERT INTO practice_records
           (user_id, question_id, user_answer, score, feedback, strengths, improvements)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            user["user_id"], req.question_id, req.user_answer,
            result["score"], result["feedback"],
            json.dumps(result.get("strengths", []), ensure_ascii=False),
            json.dumps(result.get("improvements", []), ensure_ascii=False)
        )
    )
    conn.commit()
    conn.close()

    result["standard_answer"] = question["standard_answer"]
    return result

@app.get("/api/my/records")
def my_records(user: dict = Depends(current_user)):
    conn = get_db()
    rows = conn.execute(
        """SELECT pr.id, pr.score, pr.feedback, pr.strengths, pr.improvements,
                  pr.user_answer, pr.created_at, q.title, q.category
           FROM practice_records pr
           JOIN questions q ON pr.question_id = q.id
           WHERE pr.user_id = ?
           ORDER BY pr.created_at DESC LIMIT 50""",
        (user["user_id"],)
    ).fetchall()
    conn.close()
    records = []
    for r in rows:
        d = dict(r)
        d["strengths"] = json.loads(d["strengths"])
        d["improvements"] = json.loads(d["improvements"])
        records.append(d)
    return records

@app.get("/api/my/stats")
def my_stats(user: dict = Depends(current_user)):
    conn = get_db()
    stats = conn.execute(
        """SELECT
             COUNT(*) as total_attempts,
             ROUND(AVG(score), 1) as avg_score,
             MAX(score) as best_score,
             COUNT(DISTINCT question_id) as questions_practiced
           FROM practice_records WHERE user_id = ?""",
        (user["user_id"],)
    ).fetchone()
    conn.close()
    return dict(stats)

# ─── 管理员接口 ───────────────────────────────────────────────────────────────
@app.get("/api/admin/users")
def admin_users(user: dict = Depends(admin_user)):
    conn = get_db()
    rows = conn.execute(
        """SELECT u.id, u.username, u.role, u.created_at,
                  COUNT(pr.id) as attempts,
                  ROUND(AVG(pr.score), 1) as avg_score,
                  MAX(pr.score) as best_score
           FROM users u
           LEFT JOIN practice_records pr ON u.id = pr.user_id
           GROUP BY u.id
           ORDER BY avg_score DESC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/admin/records")
def admin_records(user: dict = Depends(admin_user)):
    conn = get_db()
    rows = conn.execute(
        """SELECT pr.id, pr.score, pr.feedback, pr.user_answer, pr.created_at,
                  pr.strengths, pr.improvements,
                  u.username, q.title, q.category
           FROM practice_records pr
           JOIN users u ON pr.user_id = u.id
           JOIN questions q ON pr.question_id = q.id
           ORDER BY pr.created_at DESC LIMIT 100"""
    ).fetchall()
    conn.close()
    records = []
    for r in rows:
        d = dict(r)
        d["strengths"] = json.loads(d["strengths"])
        d["improvements"] = json.loads(d["improvements"])
        records.append(d)
    return records

@app.get("/api/admin/stats")
def admin_stats(user: dict = Depends(admin_user)):
    conn = get_db()
    overview = conn.execute(
        """SELECT
             COUNT(DISTINCT user_id) as active_users,
             COUNT(*) as total_attempts,
             ROUND(AVG(score), 1) as avg_score
           FROM practice_records"""
    ).fetchone()
    by_question = conn.execute(
        """SELECT q.title, q.category, COUNT(*) as attempts, ROUND(AVG(pr.score), 1) as avg_score
           FROM practice_records pr
           JOIN questions q ON pr.question_id = q.id
           GROUP BY q.id
           ORDER BY q.order_num"""
    ).fetchall()
    leaderboard = conn.execute(
        """SELECT u.username, COUNT(*) as attempts,
                  ROUND(AVG(pr.score), 1) as avg_score, MAX(pr.score) as best_score
           FROM practice_records pr
           JOIN users u ON pr.user_id = u.id
           GROUP BY u.id
           ORDER BY avg_score DESC LIMIT 20"""
    ).fetchall()
    conn.close()
    return {
        "overview": dict(overview),
        "by_question": [dict(r) for r in by_question],
        "leaderboard": [dict(r) for r in leaderboard]
    }

# ─── 管理员：题库管理 ─────────────────────────────────────────────────────────
@app.post("/api/admin/questions")
def admin_add_question(req: QuestionReq, user: dict = Depends(admin_user)):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO questions (category, title, scenario, standard_answer, key_points, tips, order_num) VALUES (?,?,?,?,?,?,?)",
        (req.category, req.title, req.scenario, req.standard_answer, req.key_points, req.tips, req.order_num)
    )
    conn.commit()
    qid = cur.lastrowid
    conn.close()
    return {"id": qid, "message": "题目添加成功"}

@app.put("/api/admin/questions/{qid}")
def admin_update_question(qid: int, req: QuestionReq, user: dict = Depends(admin_user)):
    conn = get_db()
    result = conn.execute(
        """UPDATE questions SET category=?, title=?, scenario=?, standard_answer=?,
           key_points=?, tips=?, order_num=? WHERE id=?""",
        (req.category, req.title, req.scenario, req.standard_answer, req.key_points, req.tips, req.order_num, qid)
    )
    conn.commit()
    conn.close()
    if result.rowcount == 0:
        raise HTTPException(404, "题目不存在")
    return {"message": "更新成功"}

@app.delete("/api/admin/questions/{qid}")
def admin_delete_question(qid: int, user: dict = Depends(admin_user)):
    conn = get_db()
    conn.execute("DELETE FROM practice_records WHERE question_id = ?", (qid,))
    result = conn.execute("DELETE FROM questions WHERE id = ?", (qid,))
    conn.commit()
    conn.close()
    if result.rowcount == 0:
        raise HTTPException(404, "题目不存在")
    return {"message": "删除成功"}

# ─── 静态文件 ─────────────────────────────────────────────────────────────────
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
def root():
    return FileResponse(str(STATIC_DIR / "index.html"))

@app.get("/app")
def app_page():
    return FileResponse(str(STATIC_DIR / "app.html"))

@app.get("/admin")
def admin_page():
    return FileResponse(str(STATIC_DIR / "admin.html"))

# ─── 启动 ─────────────────────────────────────────────────────────────────────
@app.on_event("startup")
def startup():
    init_db()
    print("=" * 50)
    print("  Tesla延保销售陪练系统 已启动")
    print("=" * 50)
    print(f"  管理员账号: admin / admin888")
    print(f"  AI评分: {'已启用 (Claude)' if ANTHROPIC_API_KEY else '未配置，使用关键词匹配'}")
    print(f"  访问地址: http://localhost:8000")
    print("=" * 50)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
