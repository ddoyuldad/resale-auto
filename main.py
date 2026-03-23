"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📦 매입건 자동화 프로그램 v1.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  전체 워크플로우:
    Step 1. 이미지 분석 → 제품별 폴더 자동 분류
    Step 2. 엑셀 자동 생성 (썸네일 + 제품 정보)
    Step 3. 네이버 쇼핑 최저가 자동 조회
    Step 4. 상세페이지 HTML 자동 생성
    Step 5. 쿠팡 등록 데이터 준비

  사용법:
    python main.py                → 메뉴 선택
    python main.py --all 폴더경로 → 전체 자동 실행
    python main.py --step 3      → 특정 단계만 실행
"""
import os, sys, json, argparse
from pathlib import Path
from datetime import datetime

# ─── 경로 설정 ────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from config import (
    ANTHROPIC_API_KEY, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET,
    COUPANG_ACCESS_KEY, COUPANG_SECRET_KEY
)

# ─── 상태 저장/복원 (이전 실행 결과 재사용) ──────────────────────
STATE_FILE = os.path.join(SCRIPT_DIR, ".run_state.json")

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# ─── 유틸리티 ─────────────────────────────────────────────────
def print_banner():
    print()
    print("━" * 60)
    print("  📦 매입건 자동화 프로그램 v1.0")
    print("━" * 60)
    print(f"  실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print()

def print_status():
    """현재 API 키 설정 상태 표시"""
    checks = [
        ("Claude AI (이미지 분석)", bool(ANTHROPIC_API_KEY)),
        ("네이버 쇼핑 API",       bool(NAVER_CLIENT_ID and NAVER_CLIENT_SECRET)),
        ("쿠팡 OPEN API",         bool(COUPANG_ACCESS_KEY and COUPANG_SECRET_KEY)),
    ]
    print("  🔑 API 설정 상태:")
    for name, ok in checks:
        icon = "✅" if ok else "❌"
        print(f"     {icon} {name}")
    print()

def print_menu():
    print("  📋 실행 메뉴:")
    print("  ─────────────────────────────────────")
    print("  [1] 이미지 분석 & 폴더 분류   (Step 1)")
    print("  [2] 엑셀 자동 생성            (Step 2)")
    print("  [3] 네이버 최저가 조회         (Step 3)")
    print("  [4] 상세페이지 생성            (Step 4)")
    print("  [5] 쿠팡 등록 데이터 준비      (Step 5)")
    print("  ─────────────────────────────────────")
    print("  [A] 전체 자동 실행 (Step 1→5)")
    print("  [S] 설정 확인 (config.py)")
    print("  [Q] 종료")
    print()

def get_source_folder(state):
    """소스 폴더 경로 입력 받기"""
    last_folder = state.get("source_folder", "")
    if last_folder and os.path.isdir(last_folder):
        print(f"  📂 이전 작업 폴더: {last_folder}")
        use_last = input("     이 폴더를 사용할까요? (y/n): ").strip().lower()
        if use_last == 'y':
            return last_folder

    while True:
        folder = input("\n  📂 이미지 폴더 경로를 입력하세요: ").strip()
        folder = folder.strip('"').strip("'")  # 따옴표 제거
        if os.path.isdir(folder):
            return folder
        print(f"     ⚠️  폴더를 찾을 수 없습니다: {folder}")

# ─── Step 실행 함수들 ─────────────────────────────────────────

def run_step1(state):
    """Step 1: 이미지 분석 & 폴더 분류"""
    folder = get_source_folder(state)
    state["source_folder"] = folder

    import step1_classify
    products = step1_classify.run(folder)

    if products:
        # 상태 저장 (파일 경로 등은 직렬화 가능한 형태로)
        state["products"] = {}
        for name, data in products.items():
            state["products"][name] = {
                "info": data["info"],
                "files": data["files"],
                "folder_path": data.get("folder_path", ""),
            }
        save_state(state)
        print(f"\n✅ Step 1 완료 — {len(products)}개 제품 분류됨")
    else:
        print("\n⚠️  Step 1 실패 — 분류된 제품이 없습니다.")

    return products

def run_step2(state, products=None):
    """Step 2: 엑셀 자동 생성"""
    if products is None:
        products = _load_products(state)
    if not products:
        return None, None

    folder = state.get("source_folder", SCRIPT_DIR)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_path = os.path.join(folder, f"매입건_제품정리_{timestamp}.xlsx")

    import step2_excel
    product_list, excel_path = step2_excel.run(products, output_path)

    state["excel_path"] = excel_path
    state["product_list"] = product_list
    save_state(state)

    return product_list, excel_path

def run_step3(state, product_list=None, excel_path=None):
    """Step 3: 네이버 최저가 조회"""
    if product_list is None:
        product_list = state.get("product_list")
    if excel_path is None:
        excel_path = state.get("excel_path")

    if not product_list or not excel_path:
        print("\n⚠️  Step 2를 먼저 실행해 주세요 (엑셀 파일 필요)")
        return None

    if not os.path.exists(excel_path):
        print(f"\n⚠️  엑셀 파일을 찾을 수 없습니다: {excel_path}")
        return None

    import step3_naver
    results = step3_naver.run(product_list, excel_path)

    state["naver_results"] = results
    save_state(state)

    return results

def run_step4(state, products=None):
    """Step 4: 상세페이지 생성"""
    if products is None:
        products = _load_products(state)
    if not products:
        return None

    folder = state.get("source_folder", SCRIPT_DIR)

    import step4_detail
    generated = step4_detail.run(products, folder)

    state["detail_pages"] = generated
    save_state(state)

    return generated

def run_step5(state, products=None, naver_results=None):
    """Step 5: 쿠팡 등록 데이터 준비"""
    if products is None:
        products = _load_products(state)
    if not products:
        return

    if naver_results is None:
        naver_results = state.get("naver_results")

    import step5_coupang
    step5_coupang.run(products, naver_results)

def _load_products(state):
    """상태에서 products 복원, 없으면 폴더에서 읽기"""
    products = state.get("products")
    if products:
        return products

    folder = state.get("source_folder")
    if folder and os.path.isdir(folder):
        print("\n📂 기존 폴더 구조에서 제품 정보를 읽어옵니다...")
        import step1_classify
        products = step1_classify.read_existing_folders(folder)
        if products:
            state["products"] = {}
            for name, data in products.items():
                state["products"][name] = {
                    "info": data["info"],
                    "files": data["files"],
                    "folder_path": data.get("folder_path", ""),
                }
            return products

    print("\n⚠️  제품 데이터가 없습니다. Step 1을 먼저 실행해 주세요.")
    return None

# ─── 전체 자동 실행 ───────────────────────────────────────────

def run_all(state):
    """Step 1~5 순차 자동 실행"""
    print("\n" + "═" * 60)
    print("  🚀 전체 자동 실행 모드 (Step 1 → 5)")
    print("═" * 60)

    # Step 1
    print("\n" + "─" * 60)
    products = run_step1(state)
    if not products:
        print("\n❌ Step 1에서 중단되었습니다.")
        return

    # Step 2
    print("\n" + "─" * 60)
    product_list, excel_path = run_step2(state, products)
    if not product_list:
        print("\n❌ Step 2에서 중단되었습니다.")
        return

    # Step 3
    print("\n" + "─" * 60)
    naver_results = run_step3(state, product_list, excel_path)

    # Step 4
    print("\n" + "─" * 60)
    run_step4(state, products)

    # Step 5
    print("\n" + "─" * 60)
    run_step5(state, products, naver_results)

    # 최종 요약
    print("\n" + "═" * 60)
    print("  🎉 전체 자동화 완료!")
    print("═" * 60)
    print(f"\n  📊 처리 결과:")
    print(f"     • 제품 분류: {len(products)}개")
    if excel_path:
        print(f"     • 엑셀 파일: {excel_path}")
    if naver_results:
        found = len([r for r in naver_results if r.get("price", 0) > 0])
        print(f"     • 최저가 조회: {found}/{len(naver_results)}개 확인")
    folder = state.get("source_folder", "")
    detail_dir = os.path.join(folder, "상세페이지")
    if os.path.isdir(detail_dir):
        print(f"     • 상세페이지: {detail_dir}/")
    print()

# ─── CLI 인터페이스 ───────────────────────────────────────────

def interactive_mode():
    """대화형 메뉴 모드"""
    print_banner()
    print_status()

    state = load_state()

    while True:
        print_menu()
        choice = input("  선택: ").strip().upper()

        if choice == '1':
            run_step1(state)
        elif choice == '2':
            run_step2(state)
        elif choice == '3':
            run_step3(state)
        elif choice == '4':
            run_step4(state)
        elif choice == '5':
            run_step5(state)
        elif choice == 'A':
            run_all(state)
        elif choice == 'S':
            print_status()
            print(f"  📁 config.py 위치: {os.path.join(SCRIPT_DIR, 'config.py')}")
            print(f"     → 이 파일을 열어서 API 키를 설정하세요\n")
        elif choice == 'Q':
            print("\n  👋 프로그램을 종료합니다.\n")
            break
        else:
            print("  ⚠️  올바른 메뉴를 선택해 주세요.\n")

def main():
    parser = argparse.ArgumentParser(description="매입건 자동화 프로그램")
    parser.add_argument("--all", metavar="폴더경로",
                        help="전체 자동 실행 (폴더 경로 지정)")
    parser.add_argument("--step", type=int, choices=[1,2,3,4,5],
                        help="특정 단계만 실행 (1~5)")
    parser.add_argument("--folder", metavar="경로",
                        help="작업 폴더 경로")
    args = parser.parse_args()

    if args.all:
        # 전체 자동 실행
        print_banner()
        state = load_state()
        state["source_folder"] = args.all
        run_all(state)
    elif args.step:
        # 특정 단계 실행
        print_banner()
        state = load_state()
        if args.folder:
            state["source_folder"] = args.folder

        step_funcs = {
            1: run_step1,
            2: run_step2,
            3: run_step3,
            4: run_step4,
            5: run_step5,
        }
        step_funcs[args.step](state)
    else:
        # 대화형 메뉴
        interactive_mode()

if __name__ == "__main__":
    main()
