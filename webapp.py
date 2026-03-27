"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📦 매입건 자동화 프로그램 v2.0 — 웹앱 버전
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  사용법:
    pip install -r requirements.txt
    python webapp.py

  → 브라우저에서 http://localhost:8080 접속
"""
import os, sys, json, shutil, glob, traceback, threading
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template, request, jsonify, send_file, send_from_directory

# ─── 경로 설정 ──────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import config
import importlib

def reload_config():
    """config.py를 항상 최신 상태로 다시 읽기"""
    importlib.reload(config)
    return config

# 초기 로드
ANTHROPIC_API_KEY = config.ANTHROPIC_API_KEY
NAVER_CLIENT_ID = config.NAVER_CLIENT_ID
NAVER_CLIENT_SECRET = config.NAVER_CLIENT_SECRET
COUPANG_ACCESS_KEY = config.COUPANG_ACCESS_KEY
COUPANG_SECRET_KEY = config.COUPANG_SECRET_KEY
COUPANG_VENDOR_ID = config.COUPANG_VENDOR_ID
THUMBNAIL_SIZE = config.THUMBNAIL_SIZE
GEMINI_API_KEY = config.GEMINI_API_KEY

app = Flask(__name__, template_folder=os.path.join(SCRIPT_DIR, "web_templates"),
            static_folder=os.path.join(SCRIPT_DIR, "web_static"))
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500MB

# ─── 상태 관리 ──────────────────────────────────────────────
STATE_FILE = os.path.join(SCRIPT_DIR, ".webapp_state.json")
UPLOAD_FOLDER = os.path.join(SCRIPT_DIR, "uploads")

# 작업 진행 상태 (실시간)
task_status = {
    "running": False,
    "step": "",
    "progress": 0,
    "message": "",
    "log": [],
}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, default=str)


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def log(msg):
    task_status["log"].append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    task_status["message"] = msg
    print(msg)


# ─── 캐시 방지 (HTML 항상 최신 버전) ─────────────────────────
@app.after_request
def add_no_cache(response):
    if 'text/html' in response.content_type:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


# ─── 라우트: 메인 페이지 ──────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


# ─── API: 설정 상태 확인 ─────────────────────────────────────
@app.route("/api/status")
def api_status():
    state = load_state()
    return jsonify({
        "api_keys": {
            "anthropic": bool(ANTHROPIC_API_KEY),
            "naver": bool(NAVER_CLIENT_ID and NAVER_CLIENT_SECRET),
            "coupang": bool(COUPANG_ACCESS_KEY and COUPANG_SECRET_KEY),
            "gemini": bool(GEMINI_API_KEY),
        },
        "source_folder": state.get("source_folder", ""),
        "products": list(state.get("products", {}).keys()),
        "product_count": len(state.get("products", {})),
        "excel_path": state.get("excel_path", ""),
        "task_status": task_status,
    })


# ─── API: 폴더 탐색기 열기 (네이티브 다이얼로그) ─────────────
@app.route("/api/browse-folder", methods=["POST"])
def api_browse_folder():
    """Windows 폴더 선택 다이얼로그를 열어서 경로 반환"""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()          # 메인 창 숨기기
        root.attributes('-topmost', True)  # 최상위로 올리기
        folder = filedialog.askdirectory(title="이미지 폴더를 선택하세요")
        root.destroy()
        if folder:
            return jsonify({"folder_path": folder})
        else:
            return jsonify({"folder_path": "", "cancelled": True})
    except Exception as e:
        return jsonify({"error": f"폴더 탐색기를 열 수 없습니다: {str(e)}"}), 500


# ─── API: 폴더 선택 ──────────────────────────────────────────
@app.route("/api/select-folder", methods=["POST"])
def api_select_folder():
    data = request.json
    folder = data.get("folder_path", "").strip().strip('"').strip("'")
    # Windows 경로 정규화
    folder = os.path.normpath(folder) if folder else ""

    if not folder:
        return jsonify({"error": "폴더 경로를 입력해 주세요."}), 400
    if not os.path.isdir(folder):
        return jsonify({"error": f"폴더를 찾을 수 없습니다: {folder}"}), 400

    # 이미지 파일 확인
    img_exts = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
    images = []
    for f in sorted(os.listdir(folder)):
        if f.lower().endswith(img_exts):
            images.append(f)

    # 서브폴더 확인 (이미 분류된 폴더가 있는지)
    subfolders = []
    for d in sorted(os.listdir(folder)):
        full = os.path.join(folder, d)
        if os.path.isdir(full) and not d.startswith('.') and d not in ('매입자동화', '상세페이지', '쿠팡등록데이터', '__pycache__'):
            sub_images = [f for f in os.listdir(full) if f.lower().endswith(img_exts)]
            if sub_images:
                subfolders.append({"name": d, "image_count": len(sub_images)})

    state = load_state()
    state["source_folder"] = folder
    save_state(state)

    return jsonify({
        "folder": folder,
        "image_count": len(images),
        "images": images[:20],  # 미리보기용 최대 20개
        "subfolders": subfolders,
    })


# ─── API: 이미지 서빙 (미리보기) ─────────────────────────────
@app.route("/api/image")
def api_image():
    path = request.args.get("path", "")
    path = os.path.normpath(path) if path else ""
    if path and os.path.isfile(path):
        return send_file(path)
    return "", 404


# ─── API: Step 1 - 이미지 분류 ───────────────────────────────
@app.route("/api/step1/classify", methods=["POST"])
def api_step1_classify():
    if task_status["running"]:
        return jsonify({"error": "이미 작업이 진행 중입니다."}), 400

    data = request.json
    mode = data.get("mode", "existing")  # existing / ai / manual
    state = load_state()
    folder = state.get("source_folder", "")

    if not folder or not os.path.isdir(folder):
        return jsonify({"error": "먼저 폴더를 선택해 주세요."}), 400

    def run_classify():
        task_status["running"] = True
        task_status["step"] = "step1"
        task_status["progress"] = 0
        task_status["log"] = []
        try:
            import step1_classify
            importlib.reload(step1_classify)

            if mode == "existing":
                log("📂 기존 폴더 구조에서 제품 정보를 읽어옵니다...")
                products = step1_classify.read_existing_folders(folder)
            elif mode == "ai":
                cfg = reload_config()
                gemini_key = cfg.GEMINI_API_KEY
                if not gemini_key:
                    log("❌ Gemini API 키가 설정되지 않았습니다. .env 파일에 GEMINI_API_KEY를 입력해 주세요.")
                    task_status["running"] = False
                    return
                log("🤖 Gemini AI 이미지 분석을 시작합니다...")
                image_files = step1_classify.get_image_files(folder)
                products_raw = step1_classify.classify_with_ai(image_files, gemini_key)
                if products_raw:
                    log("📁 폴더 정리 중...")
                    products = step1_classify.organize_files(folder, products_raw, auto_confirm=True)
                else:
                    products = None
            else:
                log("❌ 웹앱에서는 수동 분류를 지원하지 않습니다. AI 또는 기존 폴더 모드를 사용해 주세요.")
                task_status["running"] = False
                return

            if products:
                state["products"] = {}
                for name, pdata in products.items():
                    state["products"][name] = {
                        "info": pdata.get("info", {}),
                        "files": pdata.get("files", []),
                        "folder_path": pdata.get("folder_path", ""),
                    }
                save_state(state)
                log(f"✅ {len(products)}개 제품 분류 완료!")
                task_status["progress"] = 100
            else:
                log("⚠️ 분류된 제품이 없습니다.")
        except Exception as e:
            log(f"❌ 오류 발생: {str(e)}")
            traceback.print_exc()
        finally:
            task_status["running"] = False

    thread = threading.Thread(target=run_classify, daemon=True)
    thread.start()

    return jsonify({"status": "started", "mode": mode})


# ─── API: Step 2 - 엑셀 생성 ─────────────────────────────────
@app.route("/api/step2/excel", methods=["POST"])
def api_step2_excel():
    if task_status["running"]:
        return jsonify({"error": "이미 작업이 진행 중입니다."}), 400

    state = load_state()
    products = state.get("products")
    if not products:
        return jsonify({"error": "Step 1을 먼저 실행해 주세요."}), 400

    # 사용자 지정 출력 폴더
    req_data = request.get_json(silent=True) or {}
    custom_folder = req_data.get("output_folder", "").strip()

    def run_excel():
        task_status["running"] = True
        task_status["step"] = "step2"
        task_status["progress"] = 0
        task_status["log"] = []
        try:
            import step2_excel

            # 사용자 지정 폴더가 있으면 그곳에, 없으면 사진 폴더에 저장
            if custom_folder and os.path.isdir(custom_folder):
                folder = custom_folder
                log(f"📁 저장 폴더: {folder}")
            else:
                folder = state.get("source_folder", SCRIPT_DIR)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            output_path = os.path.join(folder, f"매입건_제품정리_{timestamp}.xlsx")

            log("📊 엑셀 파일 생성 중...")
            product_list, excel_path = step2_excel.run(products, output_path)

            state["excel_path"] = excel_path
            state["product_list"] = product_list
            save_state(state)

            log(f"✅ 엑셀 생성 완료: {os.path.basename(excel_path)}")
            task_status["progress"] = 100
        except Exception as e:
            log(f"❌ 오류 발생: {str(e)}")
            traceback.print_exc()
        finally:
            task_status["running"] = False

    thread = threading.Thread(target=run_excel, daemon=True)
    thread.start()

    return jsonify({"status": "started"})


# ─── API: Step 3 - 네이버 최저가 ─────────────────────────────
@app.route("/api/step3/naver", methods=["POST"])
def api_step3_naver():
    if task_status["running"]:
        return jsonify({"error": "이미 작업이 진행 중입니다."}), 400

    state = load_state()
    product_list = state.get("product_list")
    excel_path = state.get("excel_path")

    if not product_list or not excel_path:
        return jsonify({"error": "Step 2를 먼저 실행해 주세요."}), 400

    if not NAVER_CLIENT_ID:
        return jsonify({"error": "네이버 API 키가 설정되지 않았습니다."}), 400

    def run_naver():
        task_status["running"] = True
        task_status["step"] = "step3"
        task_status["progress"] = 0
        task_status["log"] = []
        try:
            import step3_naver
            importlib.reload(step3_naver)

            log("🔍 네이버 쇼핑 최저가 조회 중...")
            results = step3_naver.run(product_list, excel_path)

            state["naver_results"] = results
            save_state(state)

            if results:
                found = len([r for r in results if r.get("price", 0) > 0])
                log(f"✅ 최저가 조회 완료: {found}/{len(results)}개 확인")

            # 마진율 자동 계산 (네이버 데이터 기준)
            log("📈 마진율 계산 중...")
            import step3c_margin
            importlib.reload(step3c_margin)
            margin_results = step3c_margin.run(excel_path, product_list)
            state["margin_results"] = margin_results
            save_state(state)
            if margin_results:
                profitable = sum(1 for r in margin_results if r.get("naver_margin", 0) > 0)
                log(f"✅ 마진 계산 완료: 수익 가능 {profitable}/{len(margin_results)}개")

            task_status["progress"] = 100
        except Exception as e:
            log(f"❌ 오류 발생: {str(e)}")
            traceback.print_exc()
        finally:
            task_status["running"] = False

    thread = threading.Thread(target=run_naver, daemon=True)
    thread.start()

    return jsonify({"status": "started"})


# ─── API: Step 3-2 - 쿠팡 판매 확인 ──────────────────────
@app.route("/api/step3b/rocket", methods=["POST"])
def api_step3b_rocket():
    if task_status["running"]:
        return jsonify({"error": "이미 작업이 진행 중입니다."}), 400

    state = load_state()
    product_list = state.get("product_list")
    excel_path = state.get("excel_path")

    if not product_list or not excel_path:
        return jsonify({"error": "Step 2를 먼저 실행해 주세요."}), 400

    def run_rocket():
        task_status["running"] = True
        task_status["step"] = "step3b"
        task_status["progress"] = 0
        task_status["log"] = []
        try:
            import step3b_rocket
            importlib.reload(step3b_rocket)

            log("🛒 쿠팡 판매 확인 중...")
            results = step3b_rocket.run(product_list, excel_path)

            state["coupang_rocket_results"] = results
            save_state(state)

            if results:
                on_cnt = sum(1 for r in results if r.get("on_coupang"))
                log(f"✅ 쿠팡 조회 완료: 판매중 {on_cnt}/{len(results)}개")

            # 마진율 자동 계산
            log("📈 마진율 계산 중...")
            import step3c_margin
            importlib.reload(step3c_margin)
            margin_results = step3c_margin.run(excel_path, product_list)
            state["margin_results"] = margin_results
            save_state(state)
            if margin_results:
                profitable = sum(1 for r in margin_results if r.get("naver_margin", 0) > 0)
                log(f"✅ 마진 계산 완료: 수익 가능 {profitable}/{len(margin_results)}개")
            task_status["progress"] = 100
        except Exception as e:
            log(f"❌ 오류 발생: {str(e)}")
            traceback.print_exc()
        finally:
            task_status["running"] = False

    thread = threading.Thread(target=run_rocket, daemon=True)
    thread.start()

    return jsonify({"status": "started"})


# ─── API: Step 4 - 상세페이지 AI 이미지 생성 ─────────────────
@app.route("/api/step4/detail", methods=["POST"])
def api_step4_detail():
    if task_status["running"]:
        return jsonify({"error": "이미 작업이 진행 중입니다."}), 400

    state = load_state()
    products = state.get("products")
    if not products:
        return jsonify({"error": "Step 1을 먼저 실행해 주세요."}), 400

    # config를 최신 상태로 다시 읽기
    cfg = reload_config()
    gemini_key = cfg.GEMINI_API_KEY

    if not gemini_key:
        return jsonify({"error": "Gemini API 키가 설정되지 않았습니다. config.py에서 GEMINI_API_KEY를 입력해 주세요."}), 400

    data = request.json or {}
    model_no = data.get("model_no", 1)  # 1~4 모델 선택
    product_keys = data.get("product_keys", [])  # 빈 배열 = 전체

    # 선택된 제품만 필터링 (비어있으면 전체)
    if product_keys:
        selected_products = {k: v for k, v in products.items() if k in product_keys}
        if not selected_products:
            return jsonify({"error": "선택한 제품을 찾을 수 없습니다."}), 400
    else:
        selected_products = products

    def run_detail():
        task_status["running"] = True
        task_status["step"] = "step4"
        task_status["progress"] = 0
        task_status["log"] = []
        try:
            import step4_detail
            importlib.reload(step4_detail)  # 모듈도 최신 상태로

            folder = state.get("source_folder", SCRIPT_DIR)

            def progress_cb(msg, pct=None):
                log(msg)
                if pct is not None:
                    task_status["progress"] = pct

            model = step4_detail.get_model_by_no(model_no)
            tag = "🟢무료" if model["free"] else "🔴유료"
            cnt_str = f"{len(selected_products)}/{len(products)}개 제품" if product_keys else f"전체 {len(products)}개 제품"
            log(f"🎨 상세페이지 AI 이미지 생성 시작 ({model['name']} {tag}) — {cnt_str}")
            log(f"   🔑 Gemini API 키: {gemini_key[:10]}...{gemini_key[-4:]}")

            generated = step4_detail.run(
                selected_products, folder,
                model_no=model_no,
                api_key=gemini_key,
                progress_callback=progress_cb,
            )

            state["detail_pages"] = generated
            save_state(state)

            success = sum(1 for g in generated if g.get("success"))
            total_pages = sum(g.get("page_count", 0) for g in generated)
            log(f"✅ 상세페이지 {success}/{len(generated)}개 제품 완료 (총 {total_pages}장)")
            task_status["progress"] = 100
        except Exception as e:
            log(f"❌ 오류 발생: {str(e)}")
            traceback.print_exc()
        finally:
            task_status["running"] = False

    thread = threading.Thread(target=run_detail, daemon=True)
    thread.start()

    return jsonify({"status": "started", "model_no": model_no})


# ─── API: 후킹 이미지 단독 테스트 ─────────────────────────────
@app.route("/api/step4/hooking", methods=["POST"])
def api_step4_hooking():
    """후킹 이미지(01_hooking.png) 1장만 빠르게 생성"""
    if task_status["running"]:
        return jsonify({"error": "이미 작업이 진행 중입니다."}), 400

    state = load_state()
    products = state.get("products")
    if not products:
        return jsonify({"error": "Step 1을 먼저 실행해 주세요."}), 400

    cfg = reload_config()
    gemini_key = cfg.GEMINI_API_KEY
    if not gemini_key:
        return jsonify({"error": "Gemini API 키가 설정되지 않았습니다."}), 400

    data = request.json or {}
    product_key = data.get("product_key", "")
    model_no = data.get("model_no", 1)

    if not product_key:
        return jsonify({"error": "제품을 선택해 주세요."}), 400

    folder = state.get("source_folder", SCRIPT_DIR)

    def run_hooking():
        task_status["running"] = True
        task_status["step"] = "step4"
        task_status["progress"] = 0
        task_status["log"] = []
        try:
            import step4_detail
            importlib.reload(step4_detail)

            def progress_cb(msg, pct=None):
                log(msg)
                if pct is not None:
                    task_status["progress"] = pct

            model = step4_detail.get_model_by_no(model_no)
            tag = "🟢무료" if model["free"] else "🔴유료"
            log(f"🎯 후킹 이미지 테스트 시작 ({model['name']} {tag})")

            result = step4_detail.run_hooking_test(
                product_key, products, folder,
                model_no=model_no,
                api_key=gemini_key,
                progress_callback=progress_cb,
            )

            if result.get("success"):
                log(f"✅ 후킹 이미지 생성 완료!")
                log(f"   📁 저장 위치: {result.get('output_dir', '')}")
                task_status["hooking_result"] = result
            else:
                log(f"❌ 후킹 이미지 생성 실패: {result.get('error', '')}")

            task_status["progress"] = 100
        except Exception as e:
            log(f"❌ 오류: {str(e)}")
            traceback.print_exc()
        finally:
            task_status["running"] = False

    thread = threading.Thread(target=run_hooking, daemon=True)
    thread.start()

    return jsonify({"status": "started", "product_key": product_key})


# ─── API: 상세페이지 모델 목록 ────────────────────────────────
@app.route("/api/step4/models")
def api_step4_models():
    """상세페이지 생성에 사용 가능한 AI 모델 목록 반환"""
    import step4_detail
    models = []
    for m in step4_detail.MODELS:
        models.append({
            "no": m["no"],
            "name": m["name"],
            "free": m["free"],
            "price": m["price"],
            "quality": m["quality"],
            "speed": m["speed"],
            "desc": m["desc"],
            "cost_per_img": m["cost_per_img"],
        })
    cfg = reload_config()
    return jsonify({"models": models, "gemini_key_set": bool(cfg.GEMINI_API_KEY)})


# ─── API: Step 5 - 쿠팡 등록 데이터 ──────────────────────────
@app.route("/api/step5/coupang", methods=["POST"])
def api_step5_coupang():
    if task_status["running"]:
        return jsonify({"error": "이미 작업이 진행 중입니다."}), 400

    state = load_state()
    products = state.get("products")
    if not products:
        return jsonify({"error": "Step 1을 먼저 실행해 주세요."}), 400

    if not COUPANG_ACCESS_KEY:
        return jsonify({"error": "쿠팡 API 키가 설정되지 않았습니다."}), 400

    data = request.json
    do_register = data.get("register", False)

    def run_coupang():
        task_status["running"] = True
        task_status["step"] = "step5"
        task_status["progress"] = 0
        task_status["log"] = []
        try:
            import step5_coupang

            naver_results = state.get("naver_results")
            price_map = {}
            if naver_results:
                for r in naver_results:
                    nm = r.get("product_name", "")
                    pr = r.get("price", 0)
                    if nm and pr > 0:
                        price_map[nm] = pr

            output_dir = os.path.join(
                state.get("source_folder", SCRIPT_DIR), "쿠팡등록데이터"
            )
            os.makedirs(output_dir, exist_ok=True)

            json_files = []
            total = len(products)
            for idx, (name, pdata) in enumerate(sorted(products.items()), 1):
                info = pdata.get("info", {})
                pname = info.get("product_name", name)
                naver_price = price_map.get(pname, 0)

                log(f"📦 [{idx}/{total}] {pname} 데이터 생성 중...")

                product_data = step5_coupang.build_product_data(info, naver_price=naver_price)

                safe_name = pname.replace("/", "_").replace("\\", "_")[:30]
                preview_path = os.path.join(output_dir, f"{idx:02d}_{safe_name}.json")
                with open(preview_path, "w", encoding="utf-8") as f:
                    json.dump(product_data, f, ensure_ascii=False, indent=2)

                json_files.append(preview_path)
                task_status["progress"] = int(idx / total * 80)

            # 실제 등록
            if do_register:
                log("🚀 쿠팡 API로 실제 등록 시작...")
                import time
                for jf in json_files:
                    with open(jf, "r", encoding="utf-8") as f:
                        pd = json.load(f)
                    result = step5_coupang.register_product(pd)
                    if result:
                        log(f"   → 결과: {result.get('code', 'UNKNOWN')}")
                    time.sleep(1)

            state["coupang_json_dir"] = output_dir
            save_state(state)

            log(f"✅ 쿠팡 등록 데이터 {len(json_files)}건 생성 완료")
            task_status["progress"] = 100
        except Exception as e:
            log(f"❌ 오류 발생: {str(e)}")
            traceback.print_exc()
        finally:
            task_status["running"] = False

    thread = threading.Thread(target=run_coupang, daemon=True)
    thread.start()

    return jsonify({"status": "started"})


# ─── API: 전체 자동 실행 ─────────────────────────────────────
@app.route("/api/run-all", methods=["POST"])
def api_run_all():
    if task_status["running"]:
        return jsonify({"error": "이미 작업이 진행 중입니다."}), 400

    state = load_state()
    folder = state.get("source_folder", "")
    if not folder:
        return jsonify({"error": "먼저 폴더를 선택해 주세요."}), 400

    data = request.json
    mode = data.get("mode", "existing")

    def run_all():
        task_status["running"] = True
        task_status["log"] = []
        try:
            # Step 1
            task_status["step"] = "step1"
            task_status["progress"] = 0
            import step1_classify

            if mode == "existing":
                log("📂 [Step 1] 기존 폴더에서 제품 정보 읽기...")
                products = step1_classify.read_existing_folders(folder)
            else:
                log("🤖 [Step 1] Gemini AI 이미지 분석 시작...")
                cfg = reload_config()
                gemini_key = cfg.GEMINI_API_KEY
                if not gemini_key:
                    log("❌ Gemini API 키가 설정되지 않았습니다. .env에 GEMINI_API_KEY를 입력해 주세요.")
                    return
                image_files = step1_classify.get_image_files(folder)
                products_raw = step1_classify.classify_with_ai(image_files, gemini_key)
                if products_raw:
                    products = step1_classify.organize_files(folder, products_raw, auto_confirm=True)
                else:
                    products = None

            if not products:
                log("❌ 제품 분류 실패. 중단합니다.")
                return

            state["products"] = {}
            for name, pdata in products.items():
                state["products"][name] = {
                    "info": pdata.get("info", {}),
                    "files": pdata.get("files", []),
                    "folder_path": pdata.get("folder_path", ""),
                }
            save_state(state)
            log(f"✅ [Step 1] {len(products)}개 제품 분류 완료")
            task_status["progress"] = 20

            # Step 2
            task_status["step"] = "step2"
            import step2_excel
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            output_path = os.path.join(folder, f"매입건_제품정리_{timestamp}.xlsx")
            log("📊 [Step 2] 엑셀 생성 중...")
            product_list, excel_path = step2_excel.run(products, output_path)
            state["excel_path"] = excel_path
            state["product_list"] = product_list
            save_state(state)
            log(f"✅ [Step 2] 엑셀 생성 완료")
            task_status["progress"] = 40

            # Step 3
            task_status["step"] = "step3"
            if NAVER_CLIENT_ID:
                import step3_naver
                log("🔍 [Step 3] 네이버 최저가 조회 중...")
                results = step3_naver.run(product_list, excel_path)
                state["naver_results"] = results
                save_state(state)
                found = len([r for r in results if r.get("price", 0) > 0]) if results else 0
                log(f"✅ [Step 3] 최저가 {found}건 확인")
            else:
                log("⏭️ [Step 3] 네이버 API 키 미설정 — 건너뜀")
            task_status["progress"] = 60

            # Step 3-2
            task_status["step"] = "step3b"
            try:
                import step3b_rocket
                importlib.reload(step3b_rocket)
                log("🛒 [Step 3-2] 쿠팡 판매 확인 중...")
                rocket_results = step3b_rocket.run(product_list, excel_path)
                state["coupang_rocket_results"] = rocket_results
                save_state(state)
                if rocket_results:
                    rc = sum(1 for r in rocket_results if r.get("rocket"))
                    log(f"✅ [Step 3-2] 로켓배송 {rc}건 확인")
                else:
                    log("⏭️ [Step 3-2] 쿠팡 조회 결과 없음")
            except Exception as e:
                log(f"⚠️ [Step 3-2] 쿠팡 조회 오류: {str(e)}")
            task_status["progress"] = 65

            # Step 4
            task_status["step"] = "step4"
            import step4_detail
            if GEMINI_API_KEY:
                log("🎨 [Step 4] 상세페이지 AI 이미지 생성 중...")
                def step4_progress(msg, pct=None):
                    log(msg)
                generated = step4_detail.run(
                    products, folder,
                    model_no=1,  # 전체 자동 실행 시 무료 모델 사용
                    api_key=GEMINI_API_KEY,
                    progress_callback=step4_progress,
                )
                state["detail_pages"] = generated
                save_state(state)
                success = sum(1 for g in generated if g.get("success"))
                log(f"✅ [Step 4] 상세페이지 {success}개 제품 완료")
            else:
                log("⏭️ [Step 4] Gemini API 키 미설정 — 건너뜀")
            task_status["progress"] = 80

            # Step 5
            task_status["step"] = "step5"
            if COUPANG_ACCESS_KEY:
                import step5_coupang
                log("📦 [Step 5] 쿠팡 등록 데이터 생성 중...")
                naver_results = state.get("naver_results")
                price_map = {}
                if naver_results:
                    for r in naver_results:
                        nm = r.get("product_name", "")
                        pr = r.get("price", 0)
                        if nm and pr > 0:
                            price_map[nm] = pr

                output_dir = os.path.join(folder, "쿠팡등록데이터")
                os.makedirs(output_dir, exist_ok=True)
                for idx, (name, pdata) in enumerate(sorted(products.items()), 1):
                    info = pdata.get("info", {})
                    pname = info.get("product_name", name)
                    product_data = step5_coupang.build_product_data(info, naver_price=price_map.get(pname, 0))
                    safe_name = pname.replace("/", "_").replace("\\", "_")[:30]
                    fpath = os.path.join(output_dir, f"{idx:02d}_{safe_name}.json")
                    with open(fpath, "w", encoding="utf-8") as f:
                        json.dump(product_data, f, ensure_ascii=False, indent=2)
                log(f"✅ [Step 5] 쿠팡 등록 데이터 생성 완료")
            else:
                log("⏭️ [Step 5] 쿠팡 API 키 미설정 — 건너뜀")
            task_status["progress"] = 100

            log("🎉 전체 자동화 완료!")
        except Exception as e:
            log(f"❌ 오류 발생: {str(e)}")
            traceback.print_exc()
        finally:
            task_status["running"] = False

    thread = threading.Thread(target=run_all, daemon=True)
    thread.start()

    return jsonify({"status": "started"})


# ─── API: 작업 진행 상태 (폴링) ───────────────────────────────
@app.route("/api/task-status")
def api_task_status():
    return jsonify(task_status)


# ─── API: 전체 결과 요약 조회 ─────────────────────────────────
@app.route("/api/results")
def api_results():
    """현재까지 생성된 결과물 목록 반환"""
    state = load_state()
    folder = state.get("source_folder", "")
    results = {}

    # 제품 분류 결과
    products = state.get("products", {})
    results["products"] = []
    for name, data in sorted(products.items()):
        info = data.get("info", {})
        results["products"].append({
            "name": info.get("product_name", name),
            "brand": info.get("brand", ""),
            "image_count": len(data.get("files", [])),
            "price_tag": info.get("price_tag", ""),
        })

    # 엑셀 파일
    excel_path = state.get("excel_path", "")
    results["excel"] = {
        "exists": bool(excel_path and os.path.isfile(excel_path)),
        "path": excel_path,
        "filename": os.path.basename(excel_path) if excel_path else "",
    }

    # 네이버 최저가 결과
    naver_results = state.get("naver_results", [])
    results["naver"] = []
    if naver_results:
        for r in naver_results:
            results["naver"].append({
                "product_name": r.get("product_name", ""),
                "price": r.get("price", 0),
                "mall": r.get("mall_name", ""),
            })

    # 쿠팡 판매 확인 결과
    rocket_results = state.get("coupang_rocket_results", [])
    results["coupang_rocket"] = []
    if rocket_results:
        for r in rocket_results:
            results["coupang_rocket"].append({
                "product_name": r.get("product_name", ""),
                "coupang_price": r.get("coupang_price", 0),
                "on_coupang": r.get("on_coupang", False),
                "status_text": r.get("status_text", ""),
            })

    # 마진 분석 결과
    margin_results = state.get("margin_results", [])
    results["margin"] = []
    if margin_results:
        for r in margin_results:
            results["margin"].append({
                "product_name": r.get("product_name", ""),
                "buy_price": r.get("buy_price", 0),
                "naver_price": r.get("naver_price", 0),
                "coupang_price": r.get("coupang_price", 0),
                "naver_margin": r.get("naver_margin", 0),
                "naver_margin_pct": r.get("naver_margin_pct", 0),
                "coupang_margin": r.get("coupang_margin", 0),
                "coupang_margin_pct": r.get("coupang_margin_pct", 0),
            })

    # 상세페이지 (AI 이미지)
    detail_dir = os.path.join(folder, "상세페이지") if folder else ""
    results["detail_pages"] = []
    if detail_dir and os.path.isdir(detail_dir):
        for d in sorted(os.listdir(detail_dir)):
            dp = os.path.join(detail_dir, d)
            if os.path.isdir(dp):
                # 새 형식: PNG 이미지들
                pngs = sorted([f for f in os.listdir(dp) if f.endswith('.png')])
                # 이전 형식: HTML 파일
                htmls = [f for f in os.listdir(dp) if f.endswith('.html')]
                if pngs:
                    results["detail_pages"].append({
                        "name": d,
                        "type": "ai_images",
                        "images": [os.path.join(dp, f) for f in pngs],
                        "image_count": len(pngs),
                        "folder_path": dp,
                    })
                elif htmls:
                    results["detail_pages"].append({
                        "name": d,
                        "type": "html",
                        "html_path": os.path.join(dp, htmls[0]),
                    })

    # 쿠팡 등록 데이터
    coupang_dir = os.path.join(folder, "쿠팡등록데이터") if folder else ""
    results["coupang"] = []
    if coupang_dir and os.path.isdir(coupang_dir):
        for f in sorted(os.listdir(coupang_dir)):
            if f.endswith('.json'):
                jpath = os.path.join(coupang_dir, f)
                try:
                    with open(jpath, "r", encoding="utf-8") as jf:
                        jdata = json.load(jf)
                    sale_price = 0
                    if jdata.get("items"):
                        sale_price = jdata["items"][0].get("salePrice", 0)
                    results["coupang"].append({
                        "filename": f,
                        "path": jpath,
                        "product_name": jdata.get("sellerProductName", f),
                        "brand": jdata.get("brand", ""),
                        "sale_price": sale_price,
                        "requested": jdata.get("requested", False),
                    })
                except:
                    results["coupang"].append({"filename": f, "path": jpath, "product_name": f})

    return jsonify(results)


# ─── API: 제품 목록 조회 ─────────────────────────────────────
@app.route("/api/products")
def api_products():
    state = load_state()
    products = state.get("products", {})
    folder = state.get("source_folder", "")

    result = []
    for name, data in sorted(products.items()):
        info = data.get("info", {})
        files = data.get("files", [])

        # 대표 이미지 (1/3 지점)
        thumb = ""
        if files:
            idx = max(0, len(files) // 3 - 1)
            thumb = files[idx] if idx < len(files) else files[0]

        result.append({
            "key": name,
            "name": name,
            "product_name": info.get("product_name", name),
            "brand": info.get("brand", ""),
            "category": info.get("category", ""),
            "spec": info.get("spec", ""),
            "price_tag": info.get("price_tag", ""),
            "image_count": len(files),
            "thumbnail": thumb,
            "folder_path": data.get("folder_path", ""),
        })

    return jsonify({"products": result, "total": len(result), "folder": folder})


# ─── API: 파일 다운로드 ──────────────────────────────────────
@app.route("/api/download")
def api_download():
    path = request.args.get("path", "")
    if path and os.path.isfile(path):
        return send_file(path, as_attachment=True)
    return jsonify({"error": "파일을 찾을 수 없습니다."}), 404


# ─── 실행 ─────────────────────────────────────────────────
if __name__ == "__main__":
    # 템플릿/정적 파일 디렉토리 생성
    os.makedirs(os.path.join(SCRIPT_DIR, "web_templates"), exist_ok=True)
    os.makedirs(os.path.join(SCRIPT_DIR, "web_static"), exist_ok=True)

    print()
    print("━" * 50)
    print("  📦 매입건 자동화 웹앱 v2.0")
    print("━" * 50)
    print(f"  🌐 브라우저에서 접속: http://localhost:8080")
    print(f"  🔑 API 설정: config.py")
    print(f"  ⏹️  종료: Ctrl+C")
    print("━" * 50)
    print()

    app.run(host="0.0.0.0", port=8080, debug=False)
