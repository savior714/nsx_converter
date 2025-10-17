import os
import json
import subprocess
import zipfile
import shutil
from pathlib import Path
import tempfile
import webbrowser
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, unquote
import base64
import re


class NSXConverter:
    """NSX 변환 로직"""
    
    @staticmethod
    def fix_image_paths(html_content, attachments=None):
        """HTML 내의 이미지 경로를 실제 파일명으로 수정"""
        if not attachments:
            return html_content
        
        # ref -> 파일명 매핑 생성
        ref_to_filename = {}
        for att_id, att_info in attachments.items():
            # 이미지 파일 확인 - type 필드 또는 파일 확장자로 확인
            att_type = att_info.get('type', '').lower()
            att_name = att_info.get('name', '').lower()
            
            # image/ 로 시작하는 타입이거나, 이미지 확장자를 가진 경우
            is_image = (att_type.startswith('image/') or 
                       att_name.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg')))
            
            if is_image:
                ref = att_info.get('ref', '')
                name = att_info.get('name', '')
                if ref and name:
                    ref_to_filename[ref] = name
        
        # ref 속성이 있는 img 태그를 찾아서 src 수정
        def replace_img(match):
            full_tag = match.group(0)
            
            # ref 속성 찾기
            ref_match = re.search(r'ref="([^"]+)"', full_tag)
            if ref_match:
                ref_value = ref_match.group(1)
                if ref_value in ref_to_filename:
                    # src를 실제 이미지 경로로 교체
                    filename = ref_to_filename[ref_value]
                    new_src = f'webman/3rdparty/NoteStation/images/{filename}'
                    # src 속성 교체
                    full_tag = re.sub(
                        r'src="[^"]*"',
                        f'src="{new_src}"',
                        full_tag
                    )
            
            return full_tag
        
        # img 태그 전체를 찾아서 교체
        html_content = re.sub(r'<img[^>]*>', replace_img, html_content)
        
        return html_content
    
    @staticmethod
    def check_pandoc():
        """Pandoc 설치 확인"""
        try:
            result = subprocess.run(
                ["pandoc", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
    @staticmethod
    def sanitize_filename(name: str) -> str:
        """파일 이름으로 쓸 수 없는 문자 제거"""
        invalid = r'\/:*?"<>|'
        for ch in invalid:
            name = name.replace(ch, "_")
        return name.strip() or "untitled"
    
    @staticmethod
    def convert(nsx_path, output_path, log_callback=None):
        """NSX 파일을 Markdown으로 변환"""
        def log(msg):
            if log_callback:
                log_callback(msg)
        
        temp_dir = None
        
        try:
            log("🚀 변환 시작...")
            log(f"📂 NSX 파일: {nsx_path}")
            
            # 출력 폴더 생성
            output_dir = Path(output_path)
            output_dir.mkdir(parents=True, exist_ok=True)
            log(f"📁 출력 폴더: {output_dir.resolve()}")
            
            # 임시 폴더에 압축 해제
            temp_dir = Path(tempfile.mkdtemp())
            log("📦 NSX 파일 압축 해제 중...")
            
            with zipfile.ZipFile(nsx_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            log("✅ 압축 해제 완료")
            
            # Pandoc 사용 가능 여부
            use_pandoc = NSXConverter.check_pandoc()
            if use_pandoc:
                log("✅ Pandoc 발견 - Markdown으로 변환합니다.")
            else:
                log("⚠️ Pandoc 없음 - HTML 파일로 저장합니다.")
            
            # 이미지 폴더 구조 생성
            images_dir = output_dir / "webman" / "3rdparty" / "NoteStation" / "images"
            images_dir.mkdir(parents=True, exist_ok=True)
            
            # 이미지-md5 매핑 수집 (같은 MD5에 여러 파일명 지원)
            image_mapping = {}  # {md5: [names]}
            image_count = 0
            
            log("🖼️ 이미지 정보 수집 중...")
            
            # 모든 노트 파일에서 attachment 정보 수집
            for folder, _, files in os.walk(temp_dir):
                for file in files:
                    file_path = Path(folder) / file
                    # 확장자 없는 파일만 확인 (file_로 시작하는 것 제외)
                    if file_path.suffix == "" and not file_path.name.startswith('file_'):
                        try:
                            text = file_path.read_text(encoding="utf-8", errors="ignore")
                            # JSON 파일인지 확인
                            if not text.strip().startswith('{'):
                                continue
                            
                            data = json.loads(text)
                            # category가 note인 것만 처리
                            if data.get('category') != 'note':
                                continue
                            
                            attachments = data.get("attachment", {})
                            if not attachments:
                                continue
                            
                            for att_id, att_info in attachments.items():
                                # 이미지 파일 확인 - type 필드 또는 파일 확장자로 확인
                                att_type = att_info.get('type', '').lower()
                                att_name = att_info.get('name', '').lower()
                                
                                # image/ 로 시작하는 타입이거나, 이미지 확장자를 가진 경우
                                is_image = (att_type.startswith('image/') or 
                                           att_name.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg')))
                                
                                if is_image:
                                    md5 = att_info.get('md5')
                                    name = att_info.get('name', 'unknown')
                                    if md5 and name:
                                        if md5 not in image_mapping:
                                            image_mapping[md5] = []
                                        # 중복 방지
                                        if name not in image_mapping[md5]:
                                            image_mapping[md5].append(name)
                        except:
                            continue
            
            total_images = sum(len(names) for names in image_mapping.values())
            log(f"📊 {total_images}개의 이미지 정보 수집 완료 (고유 MD5: {len(image_mapping)}개)")
            
            # file_<md5> 파일들을 모든 이미지 이름으로 복사
            log("📁 이미지 파일 복사 중...")
            for folder, _, files in os.walk(temp_dir):
                for file in files:
                    if file.startswith('file_'):
                        md5_hash = file.replace('file_', '')
                        if md5_hash in image_mapping:
                            source_file = Path(folder) / file
                            
                            # 같은 MD5를 가진 모든 파일명으로 복사
                            for name in image_mapping[md5_hash]:
                                target_file = images_dir / name
                                
                                try:
                                    shutil.copy2(source_file, target_file)
                                    image_count += 1
                                except Exception as e:
                                    log(f"⚠️ 이미지 복사 실패: {name}")
            
            if image_count > 0:
                log(f"✅ {image_count}개 이미지 파일 복사 완료")
            else:
                log("ℹ️ 이미지 파일이 없습니다")
            
            # 노트 파일 찾기 및 변환
            note_count = 0
            error_count = 0
            
            log("🔍 노트 파일 검색 및 변환 중...")
            
            for folder, _, files in os.walk(temp_dir):
                for file in files:
                    file_path = Path(folder) / file
                    
                    # 확장자 없는 파일만 확인 (file_로 시작하는 것 제외)
                    if file_path.suffix == "" and not file_path.name.startswith('file_'):
                        try:
                            text = file_path.read_text(encoding="utf-8", errors="ignore")
                            
                            # JSON 파일인지 확인
                            if not text.strip().startswith('{'):
                                continue
                            
                            data = json.loads(text)
                            
                            # category가 note인 것만 처리
                            if data.get('category') != 'note':
                                continue
                            
                            if '"content"' not in text:
                                continue
                            title = NSXConverter.sanitize_filename(data.get("title", "untitled"))
                            html_content = data.get("content", "")
                            attachments = data.get("attachment", {})
                            
                            if not html_content:
                                continue
                            
                            # 이미지 경로 수정 (attachment 정보 전달)
                            html_content = NSXConverter.fix_image_paths(html_content, attachments)
                            
                            if use_pandoc:
                                temp_html = output_dir / f"{title}_temp.html"
                                md_file = output_dir / f"{title}.md"
                                
                                counter = 1
                                while md_file.exists():
                                    md_file = output_dir / f"{title}_{counter}.md"
                                    counter += 1
                                
                                with open(temp_html, "w", encoding="utf-8") as h:
                                    h.write(html_content)
                                
                                result = subprocess.run(
                                    ["pandoc", "-f", "html", "-t", "markdown",
                                     str(temp_html), "-o", str(md_file)],
                                    capture_output=True,
                                    text=True
                                )
                                
                                temp_html.unlink()
                                
                                if result.returncode == 0:
                                    log(f"✅ {title}.md")
                                    note_count += 1
                                else:
                                    log(f"❌ {title}: Pandoc 변환 실패")
                                    error_count += 1
                            else:
                                html_file = output_dir / f"{title}.html"
                                
                                counter = 1
                                while html_file.exists():
                                    html_file = output_dir / f"{title}_{counter}.html"
                                    counter += 1
                                
                                with open(html_file, "w", encoding="utf-8") as h:
                                    h.write(html_content)
                                
                                log(f"✅ {title}.html")
                                note_count += 1
                        
                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            log(f"❌ {file_path.name}: {str(e)}")
                            error_count += 1
            
            log("="*50)
            log(f"✅ 변환 완료! 성공: {note_count}개 노트")
            if image_count > 0:
                log(f"🖼️ 이미지: {image_count}개 (webman 폴더에 저장)")
            if error_count > 0:
                log(f"⚠️ 실패: {error_count}개")
            log(f"📁 저장 위치: {output_dir.resolve()}")
            log("="*50)
            
            return True, note_count, error_count
        
        except zipfile.BadZipFile:
            log("❌ 오류: 유효하지 않은 NSX 파일입니다.")
            return False, 0, 0
        except Exception as e:
            log(f"❌ 오류 발생: {str(e)}")
            return False, 0, 0
        finally:
            if temp_dir and temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                    log("🧹 임시 폴더 정리 완료")
                except Exception as e:
                    log(f"⚠️ 임시 폴더 정리 실패: {str(e)}")


class WebGUIHandler(BaseHTTPRequestHandler):
    """웹 GUI 핸들러"""
    
    log_messages = []
    
    def log_message(self, format, *args):
        """서버 로그 숨기기"""
        pass
    
    def do_GET(self):
        """GET 요청 처리"""
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(self.get_html().encode('utf-8'))
        elif self.path == '/logs':
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            logs = '\n'.join(WebGUIHandler.log_messages)
            self.wfile.write(json.dumps({'logs': logs}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        """POST 요청 처리"""
        if self.path == '/convert':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            params = parse_qs(post_data)
            
            nsx_path = params.get('nsx_path', [''])[0]
            output_path = params.get('output_path', [''])[0]
            
            WebGUIHandler.log_messages = []
            
            def log_callback(msg):
                WebGUIHandler.log_messages.append(msg)
            
            # 변환 실행
            success, note_count, error_count = NSXConverter.convert(
                nsx_path, output_path, log_callback
            )
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            
            response = {
                'success': success,
                'note_count': note_count,
                'error_count': error_count,
                'logs': '\n'.join(WebGUIHandler.log_messages)
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
    
    def get_html(self):
        """HTML 페이지 생성"""
        return '''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NSX to Markdown 변환기</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 800px;
            width: 100%;
            padding: 40px;
        }
        
        h1 {
            color: #333;
            text-align: center;
            margin-bottom: 10px;
            font-size: 32px;
        }
        
        .subtitle {
            text-align: center;
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }
        
        .form-group {
            margin-bottom: 25px;
        }
        
        label {
            display: block;
            margin-bottom: 8px;
            color: #333;
            font-weight: 600;
            font-size: 14px;
        }
        
        input[type="text"] {
            width: 100%;
            padding: 12px 15px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.3s;
        }
        
        input[type="text"]:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .btn {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 18px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(0,0,0,0.2);
        }
        
        .btn:active {
            transform: translateY(0);
        }
        
        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        
        .log-container {
            margin-top: 30px;
            background: #f5f5f5;
            border-radius: 8px;
            padding: 20px;
            max-height: 400px;
            overflow-y: auto;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 12px;
            line-height: 1.6;
            white-space: pre-wrap;
            display: none;
        }
        
        .log-container.active {
            display: block;
        }
        
        .spinner {
            display: none;
            text-align: center;
            margin-top: 20px;
        }
        
        .spinner.active {
            display: block;
        }
        
        .spinner div {
            width: 40px;
            height: 40px;
            margin: 0 auto;
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .alert {
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: none;
        }
        
        .alert.success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        
        .alert.error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        
        .alert.active {
            display: block;
        }
        
        .hint {
            font-size: 12px;
            color: #999;
            margin-top: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🗒️ NSX to Markdown</h1>
        <p class="subtitle">Synology Note Station 백업 파일을 Markdown으로 변환</p>
        
        <div id="alert" class="alert"></div>
        
        <form id="convertForm">
            <div class="form-group">
                <label for="nsx_path">📂 NSX 파일 경로</label>
                <input type="text" id="nsx_path" name="nsx_path" 
                       placeholder="예: C:\\Users\\user\\Documents\\backup.nxs" required>
                <div class="hint">전체 경로를 입력하세요 (파일 탐색기에서 복사 가능)</div>
            </div>
            
            <div class="form-group">
                <label for="output_path">📁 출력 폴더</label>
                <input type="text" id="output_path" name="output_path" 
                       placeholder="예: C:\\Users\\user\\Documents\\converted_notes">
                <div class="hint">비워두면 현재 폴더의 'converted_notes'에 저장됩니다</div>
            </div>
            
            <button type="submit" class="btn" id="convertBtn">
                🔄 변환 시작
            </button>
        </form>
        
        <div class="spinner" id="spinner">
            <div></div>
            <p style="margin-top: 10px; color: #667eea;">변환 중...</p>
        </div>
        
        <div class="log-container" id="logContainer"></div>
    </div>
    
    <script>
        const form = document.getElementById('convertForm');
        const spinner = document.getElementById('spinner');
        const logContainer = document.getElementById('logContainer');
        const alert = document.getElementById('alert');
        const convertBtn = document.getElementById('convertBtn');
        
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const nsx_path = document.getElementById('nsx_path').value.trim();
            let output_path = document.getElementById('output_path').value.trim();
            
            if (!output_path) {
                output_path = 'converted_notes';
            }
            
            // UI 업데이트
            convertBtn.disabled = true;
            spinner.classList.add('active');
            logContainer.classList.add('active');
            logContainer.textContent = '변환을 시작합니다...\\n';
            alert.classList.remove('active');
            
            try {
                const response = await fetch('/convert', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: `nsx_path=${encodeURIComponent(nsx_path)}&output_path=${encodeURIComponent(output_path)}`
                });
                
                const result = await response.json();
                
                // 로그 표시
                logContainer.textContent = result.logs;
                
                // 결과 알림
                if (result.success) {
                    alert.className = 'alert success active';
                    alert.textContent = `✅ 변환 완료! ${result.note_count}개의 노트가 변환되었습니다.`;
                } else {
                    alert.className = 'alert error active';
                    alert.textContent = '❌ 변환에 실패했습니다. 로그를 확인하세요.';
                }
                
            } catch (error) {
                alert.className = 'alert error active';
                alert.textContent = `❌ 오류 발생: ${error.message}`;
                logContainer.textContent += `\\n오류: ${error.message}`;
            } finally {
                spinner.classList.remove('active');
                convertBtn.disabled = false;
            }
        });
    </script>
</body>
</html>'''


def start_server(port=8080):
    """웹 서버 시작"""
    server = HTTPServer(('localhost', port), WebGUIHandler)
    print(f"\n✅ 서버가 시작되었습니다!")
    print(f"🌐 브라우저가 자동으로 열립니다...")
    print(f"📍 주소: http://localhost:{port}")
    print(f"\n종료하려면 Ctrl+C를 누르세요.\n")
    
    # 브라우저 자동 열기
    threading.Timer(1.0, lambda: webbrowser.open(f'http://localhost:{port}')).start()
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n서버를 종료합니다...")
        server.shutdown()


if __name__ == "__main__":
    import sys
    import io
    
    # Windows 콘솔 인코딩 설정
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("="*60)
    print("🗒️  Synology Note Station → Markdown 변환기 (Web GUI)")
    print("="*60)
    start_server()

