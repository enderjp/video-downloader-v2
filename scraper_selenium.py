from selenium import webdriver
from selenium.webdriver import Remote
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
try:
    from webdriver_manager.core.utils import ChromeType
except Exception:
    try:
        from webdriver_manager.utils import ChromeType
    except Exception:
        ChromeType = None
import subprocess
from bs4 import BeautifulSoup
import json
import time
import logging
import requests
import os
from typing import Dict, List, Optional
import re
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FacebookSeleniumScraper:
    """Scraper de Facebook usando Selenium - SIN LOGIN requerido"""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.driver = None
        
    def setup_driver(self):
        """Configura el driver de Chrome"""
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument("--headless=new")
        
        # Opciones para evitar detección
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Deshabilitar notificaciones
        prefs = {
            "profile.default_content_setting_values.notifications": 2,
            "profile.managed_default_content_settings.images": 2  # Deshabilitar imágenes para más velocidad (opcional)
        }
        chrome_options.add_experimental_option("prefs", prefs)
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        # Permitir override de la ruta del binario de Chrome (útil en Docker)
        chrome_bin = os.environ.get('CHROME_BIN')
        if chrome_bin:
            chrome_options.binary_location = chrome_bin
        
        try:
            # Habilitar logging de performance para capturar requests de red
            chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

            # Detect Chrome/Chromium binary and try to download matching chromedriver
            chrome_bin = os.environ.get('CHROME_BIN', '/usr/bin/chromium')
            chrome_version = None
            try:
                out = subprocess.check_output([chrome_bin, '--version'], stderr=subprocess.STDOUT, text=True)
                chrome_version = out.strip()
                logger.info(f"Detected browser version: {chrome_version}")
            except Exception:
                logger.debug("Could not detect chrome binary version via subprocess")

            # Use webdriver-manager specifying Chromium type to better match binary
            driver_override = os.environ.get('CHROMEDRIVER_PATH')
            try:
                driver_path = None
                attempts = []

                # Extract full and major versions if possible
                full_ver = None
                major_ver = None
                try:
                    if chrome_version:
                        m_full = re.search(r'(\d+\.\d+\.\d+\.\d+)', chrome_version)
                        if m_full:
                            full_ver = m_full.group(1)
                        m_maj = re.search(r'(\d+)', chrome_version)
                        if m_maj:
                            major_ver = m_maj.group(1)
                except Exception:
                    pass

                # Try matching driver by full version, then major version, with Chromium hint
                if ChromeType is not None:
                    if full_ver:
                        attempts.append(f"chrome_type=ChromeType.CHROMIUM, version={full_ver}")
                        try:
                            driver_path = ChromeDriverManager(chrome_type=ChromeType.CHROMIUM, version=full_ver).install()
                        except Exception:
                            driver_path = None
                    if not driver_path and major_ver:
                        attempts.append(f"chrome_type=ChromeType.CHROMIUM, version_prefix={major_ver}")
                        try:
                            driver_path = ChromeDriverManager(chrome_type=ChromeType.CHROMIUM, version=major_ver).install()
                        except Exception:
                            driver_path = None

                # Try with string hint for chromium
                if not driver_path:
                    try:
                        if full_ver:
                            attempts.append(f"chrome_type='chromium', version={full_ver}")
                            driver_path = ChromeDriverManager(chrome_type='chromium', version=full_ver).install()
                        if not driver_path and major_ver:
                            attempts.append(f"chrome_type='chromium', version_prefix={major_ver}")
                            driver_path = ChromeDriverManager(chrome_type='chromium', version=major_ver).install()
                    except Exception:
                        driver_path = None

                if driver_override and os.path.exists(driver_override):
                    driver_path = driver_override
                    attempts.insert(0, 'env.CHROMEDRIVER_PATH')

                # Final fallback: default manager
                if not driver_path:
                    attempts.append('default')
                    driver_path = ChromeDriverManager().install()

                logger.info(f"Using chromedriver at: {driver_path} (attempts: {attempts})")
            except Exception as e:
                logger.warning(f"webdriver-manager failed to install chromedriver with Chromium hint: {e}; falling back to default manager")
                driver_path = ChromeDriverManager().install()

            try:
                if not driver_path or not os.path.exists(driver_path):
                    logger.warning("chromedriver path missing; downloading default via webdriver-manager")
                    driver_path = ChromeDriverManager().install()
                service = Service(driver_path)
            except Exception as service_err:
                logger.error(f"Failed to initialize chromedriver service: {service_err}")
                raise

            # If SELENIUM_REMOTE_URL is provided, connect to a remote Selenium server
            remote_url = os.environ.get('SELENIUM_REMOTE_URL')
            if remote_url:
                try:
                    logger.info(f"Connecting to remote Selenium at {remote_url}")
                    self.driver = Remote(command_executor=remote_url, options=chrome_options)
                except Exception as e:
                    logger.warning(f"Remote WebDriver connection failed: {e}; falling back to local chromedriver")
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Ocultar webdriver
            self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                """
            })
            
            logger.info("✅ Driver de Chrome configurado correctamente")
            
        except Exception as e:
            logger.error(f"❌ Error configurando driver: {e}")
            raise
    
    def parse_facebook_url(self, url: str) -> Dict[str, Optional[str]]:
        """Parsea una URL de Facebook"""
        try:
            parsed = urlparse(url)
            path = parsed.path
            
            result = {'page_name': None, 'post_id': None, 'url_type': None}
            
            # /PageName/posts/PostID
            match = re.search(r'/([^/]+)/posts/([^/?]+)', path)
            if match:
                result['page_name'] = match.group(1)
                result['post_id'] = match.group(2)
                result['url_type'] = 'post'
                return result
            
            # /PageName/photos/*/PostID
            match = re.search(r'/([^/]+)/photos/[^/]+/([^/?]+)', path)
            if match:
                result['page_name'] = match.group(1)
                result['post_id'] = match.group(2)
                result['url_type'] = 'photo'
                return result
            
            return result
            
        except Exception as e:
            logger.error(f"Error parseando URL: {e}")
            return {'page_name': None, 'post_id': None, 'url_type': None}
    
    def convert_to_mobile_url(self, url: str) -> str:
        """Convierte URL a versión móvil (más fácil de scrapear)"""
        # Asegurarse de tener esquema
        if not url.startswith('http'):
            url = 'https://' + url

        parsed = urlparse(url)
        netloc = parsed.netloc.lower()

        # Quitar prefijo www. si existe
        if netloc.startswith('www.'):
            netloc = netloc[4:]

        # Añadir subdominio móvil solo si no está presente
        if not netloc.startswith('m.'):
            netloc = 'm.' + netloc

        mobile_parsed = parsed._replace(netloc=netloc)
        return urlunparse(mobile_parsed)

    def normalize_video_url(self, url: str) -> str:
        """Remove bytestart/byteend query params to attempt a full video URL."""
        try:
            parsed = urlparse(url)
            qs = parse_qsl(parsed.query, keep_blank_values=True)
            qs = [(k, v) for (k, v) in qs if k not in ('bytestart', 'byteend')]
            new_query = urlencode(qs, doseq=True)
            return urlunparse(parsed._replace(query=new_query))
        except Exception:
            return url
    
    def scrape_post_by_url(self, post_url: str) -> Dict:
        """
        Extrae información de un post usando su URL completa
        
        Args:
            post_url: URL del post de Facebook
            
        Returns:
            Dict con información del post
        """
        if not self.driver:
            self.setup_driver()
        
        try:
            # Convertir a URL móvil (más fácil de parsear)
            mobile_url = self.convert_to_mobile_url(post_url)
            
            logger.info(f"🔍 Accediendo a: {mobile_url}")
            self.driver.get(mobile_url)
            time.sleep(3)
            
            # Scroll para cargar contenido
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Obtener HTML
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Extraer imágenes
            images = []
            img_tags = soup.find_all('img')
            
            for img in img_tags:
                src = img.get('src')
                if src and 'scontent' in src:
                    # Filtrar iconos y emojis
                    if not any(x in src for x in ['emoji', 'static', 'safe_image', 'rsrc.php']):
                        if src not in images:
                            images.append(src)
            
            # También buscar en atributos data-src
            for img in soup.find_all('img', attrs={'data-src': True}):
                src = img.get('data-src')
                if src and 'scontent' in src and src not in images:
                    images.append(src)
            
            # Extraer texto del post
            post_text = ""
            try:
                # En móvil, el texto suele estar en divs específicos
                text_divs = soup.find_all('div', {'data-ft': True})
                for div in text_divs:
                    text = div.get_text(strip=True)
                    if len(text) > 20 and len(text) > len(post_text):
                        post_text = text
                
                # Si no se encontró, buscar en cualquier div
                if not post_text:
                    all_text = soup.get_text()
                    lines = [line.strip() for line in all_text.split('\n') if len(line.strip()) > 30]
                    if lines:
                        post_text = lines[0]
                        
            except Exception as e:
                logger.warning(f"No se pudo extraer texto: {e}")
            
            # Información adicional
            parsed_info = self.parse_facebook_url(post_url)
            
            result = {
                'success': True,
                'url': post_url,
                'mobile_url': mobile_url,
                'parsed': parsed_info,
                'post': {
                    'text': post_text[:500] if post_text else "",
                    'images': [{'url': img} for img in images],
                    'total_images': len(images),
                    'page_name': parsed_info.get('page_name'),
                    'post_id': parsed_info.get('post_id')
                }
            }
            
            logger.info(f"✅ Encontradas {len(images)} imágenes")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error scrapeando post: {e}")
            return {
                'success': False,
                'error': str(e),
                'url': post_url,
                'post': None
            }

    def extract_video_url(self, soup, page_source: Optional[str] = None) -> Optional[str]:
        """Intentos heurísticos para extraer la URL del video de una publicación.

        Busca meta tags `og:video`, tags `<video>` y patrones en el HTML como `playable_url`.
        """
        try:
            # 1) Meta tags og:video
            meta = soup.find('meta', property='og:video') or soup.find('meta', property='og:video:url')
            if meta and meta.get('content'):
                return meta.get('content')

            # 2) Video tag directo
            video_tag = soup.find('video')
            if video_tag:
                src = video_tag.get('src') or video_tag.get('data-src')
                if src:
                    return src

                # <source> dentro de <video>
                source = video_tag.find('source') if video_tag else None
                if source and source.get('src'):
                    return source.get('src')

            # 3) Buscar atributos data-store o JSON con playable_url en el HTML
            if page_source:
                m = re.search(r'"playable_url":"(https:[^\"]+)"', page_source)
                if m:
                    return m.group(1).replace('\\u0025','%')

                # Variantes comunes que Facebook usa
                for pattern in [
                    r'"playable_url_quality_hd":"(https:[^\"]+)"',
                    r'"playable_url_quality_sd":"(https:[^\"]+)"',
                    r'"hd_src":"(https:[^\"]+)"',
                    r'"sd_src":"(https:[^\"]+)"',
                    r'"sd_src_no_ratelimit":"(https:[^\"]+)"',
                    r'"hd_src_no_ratelimit":"(https:[^\"]+)"',
                    r'"fallback_playable_url":"(https:[^\"]+)"',
                    r'src\\":\"(https://video[^\"]+)'
                ]:
                    mm = re.search(pattern, page_source)
                    if mm:
                        return mm.group(1).replace('\\u0025','%')

            # 4) Buscar enlaces que indiquen video en href
            for a in soup.find_all('a', href=True):
                href = a['href']
                if 'video.php' in href or ('play' in href and 'fbcdn' in href):
                    if href.startswith('/'):
                        return 'https://m.facebook.com' + href
                    return href

            # 5) Buscar directamente URLs fbcdn en el HTML
            m_fbcdn = re.search(r'(https://[a-z0-9.\-]*fbcdn\.net[^"\'>\s]+)', page_source or '')
            if m_fbcdn:
                return m_fbcdn.group(1)

        except Exception as e:
            logger.warning(f"Error extrayendo video: {e}")

        return None

    def rank_video_candidates(self, candidates: List[str], referer: Optional[str] = None, cookies: Optional[Dict[str, str]] = None) -> Optional[str]:
        """Rank and pick the best video URL from candidates.

        Scoring rules (simple heuristics):
        - +100 if URL contains '.mp4' or '.m3u8'
        - +50 if domain contains 'video.fsci'
        - +30 if contains 'fbcdn.net'
        - +20 if contains '_nc_ht=video' or 'nc_ht=video'
        - +size_in_MB (from Content-Length via HEAD) as tie-breaker
        """
        if not candidates:
            return None

        scores = {}
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        if referer:
            headers["Referer"] = referer

        for url in set(candidates):
            score = 0
            low = url.lower()
            if '.mp4' in low or '.m3u8' in low:
                score += 100
            if 'video.fsci' in low:
                score += 50
            if 'fbcdn.net' in low:
                score += 30
            if '_nc_ht=video' in low or 'nc_ht=video' in low:
                score += 20
            # Penalizar URLs de segmentos parciales
            if 'bytestart=' in low or 'byteend=' in low:
                score -= 40

            size_mb = 0.0
            try:
                r = requests.head(url, headers=headers, cookies=cookies, allow_redirects=True, timeout=5)
                cl = r.headers.get('Content-Length')
                if cl and cl.isdigit():
                    size_mb = int(cl) / (1024 * 1024)
                    score += min(50, size_mb)
            except Exception:
                pass

            scores[url] = score

        # Order candidates by score desc
        ordered = sorted(scores.items(), key=lambda kv: (kv[1], len(kv[0])), reverse=True)

        # Validate candidates by fetching a small range to ensure it's not an empty/segment resource
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", 'Range': 'bytes=0-200000'}
        if referer:
            headers["Referer"] = referer
        for url, sc in ordered:
            try:
                r = requests.get(url, headers=headers, cookies=cookies, allow_redirects=True, timeout=8)
                content_len = len(r.content) if r.content is not None else 0
                # Heuristics: accept if we retrieved a reasonable chunk (>16KB) or server reports large content-length
                cl = r.headers.get('Content-Length')
                cl_val = int(cl) if cl and cl.isdigit() else 0
                if content_len > 16000 or cl_val > 16000:
                    return url
            except Exception:
                continue

        # Fallback: return highest scored even if validation failed
        best = max(scores.items(), key=lambda kv: (kv[1], len(kv[0])))
        return best[0]

    def _get_requests_cookies(self) -> Dict[str, str]:
        """Convierte cookies del navegador a formato requests."""
        try:
            if not self.driver:
                return {}
            cookies = {}
            for c in self.driver.get_cookies():
                if c.get('name') and c.get('value'):
                    cookies[c['name']] = c['value']
            return cookies
        except Exception:
            return {}

    def probe_video_url(self, url: str, referer: Optional[str] = None, cookies: Optional[Dict[str, str]] = None, extra_headers: Optional[Dict[str, str]] = None) -> Dict:
        """Verifica si la URL de video es accesible y retorna metadatos básicos.

        Intenta HEAD y luego GET con Range=bytes=0-1. Retorna status, content-type y content-length.
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        }
        if referer:
            headers["Referer"] = referer
        if extra_headers:
            headers.update(extra_headers)

        result = {
            "ok": False,
            "status": None,
            "content_type": None,
            "content_length": None,
            "used_referer": referer or None,
            "error": None,
        }

        try:
            r = requests.head(url, headers=headers, cookies=cookies, allow_redirects=True, timeout=8)
            result["status"] = r.status_code
            result["content_type"] = r.headers.get("Content-Type")
            result["content_length"] = r.headers.get("Content-Length")
            if r.status_code in (200, 206):
                result["ok"] = True
                return result
        except Exception as e:
            result["error"] = str(e)

        try:
            headers_range = dict(headers)
            headers_range["Range"] = "bytes=0-200000"
            r = requests.get(url, headers=headers_range, cookies=cookies, allow_redirects=True, timeout=8)
            result["status"] = r.status_code
            result["content_type"] = r.headers.get("Content-Type")
            result["content_length"] = r.headers.get("Content-Length")
            if r.status_code in (200, 206):
                result["ok"] = True
        except Exception as e:
            if not result.get("error"):
                result["error"] = str(e)

        return result

    def scrape_video_by_url(self, post_url: str) -> Dict:
        """Extrae la URL del video (si existe) de una publicación de Facebook."""
        if not self.driver:
            self.setup_driver()

        try:
            mobile_url = self.convert_to_mobile_url(post_url)
            logger.info(f"🔍 Accediendo (video): {mobile_url}")
            self.driver.get(mobile_url)
            time.sleep(3)

            # Cargar HTML y usar heurísticos
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')

            video_url = self.extract_video_url(soup, page_source=page_source)

            # Collect candidates set (from initial extract if non-blob)
            candidates = set()
            network_headers = {}
            if video_url and not str(video_url).startswith('blob:'):
                candidates.add(video_url)

            # If initial returned a blob or we want more candidates, try to play and gather resources
            try:
                try:
                    self.driver.execute_script("var v=document.querySelector('video'); if(v){v.play();}")
                except Exception:
                    pass
                time.sleep(3)
                try:
                    entries = self.driver.execute_script("return performance.getEntriesByType('resource').map(e => e.name);")
                except Exception:
                    entries = self.driver.execute_script("return performance.getEntries().map(e => e.name || e.entryType || '');")

                if entries:
                    for ent in entries:
                        if not ent:
                            continue
                        if ent.startswith('blob:'):
                            continue
                        low = ent.lower()
                        if '.mp4' in low or '.m3u8' in low or 'video.fsci' in low:
                            candidates.add(ent)
                            normalized = self.normalize_video_url(ent)
                            if normalized != ent:
                                candidates.add(normalized)
            except Exception:
                pass

            # Intentar reproducir el video para forzar la carga de recursos y luego revisar performance entries
            if not video_url:
                try:
                    # intentar play por JS
                    try:
                        self.driver.execute_script("var v=document.querySelector('video'); if(v){v.play();}")
                    except Exception:
                        pass

                    time.sleep(4)

                    # obtener recursos cargados
                    try:
                        entries = self.driver.execute_script("return performance.getEntriesByType('resource').map(e => e.name);")
                    except Exception:
                        entries = self.driver.execute_script("return performance.getEntries().map(e => e.name || e.entryType || '');")

                    if entries:
                        for ent in entries:
                            if not ent:
                                continue
                            if ent.startswith('blob:'):
                                continue
                            candidates.add(ent)
                except Exception as e:
                    logger.debug(f"No se pudo obtener performance entries: {e}")

                # Finalmente intentar leer los performance logs (CDP) para capturar requests network
                try:
                    logs = self.driver.get_log('performance')
                    for entry in logs:
                        try:
                            msg = json.loads(entry['message'])['message']
                            method = msg.get('method', '')
                            params = msg.get('params', {})
                            if method == 'Network.requestWillBeSent':
                                req = params.get('request', {})
                                url_seen = req.get('url')
                                if url_seen and not url_seen.startswith('blob:'):
                                    low = url_seen.lower()
                                    if '.mp4' in low or '.m3u8' in low or 'video.fsci' in low:
                                        candidates.add(url_seen)
                                        normalized = self.normalize_video_url(url_seen)
                                        if normalized != url_seen:
                                            candidates.add(normalized)
                                    hdrs = req.get('headers', {}) or {}
                                    if isinstance(hdrs, dict):
                                        network_headers[url_seen] = {k: str(v) for k, v in hdrs.items()}
                            elif method == 'Network.responseReceived':
                                url_seen = params.get('response', {}).get('url')
                                if url_seen and not url_seen.startswith('blob:'):
                                    low = url_seen.lower()
                                    if '.mp4' in low or '.m3u8' in low or 'video.fsci' in low:
                                        candidates.add(url_seen)
                                        normalized = self.normalize_video_url(url_seen)
                                        if normalized != url_seen:
                                            candidates.add(normalized)
                        except Exception:
                            continue
                except Exception as e:
                    logger.debug(f"No se pudo leer performance logs: {e}")

            # Si tenemos candidatos, rankear y devolver mejor
            if candidates:
                cookie_jar = self._get_requests_cookies()
                best = self.rank_video_candidates(list(candidates), referer=post_url, cookies=cookie_jar)
                if best:
                    extra_headers = network_headers.get(best)
                    probe = self.probe_video_url(best, referer=post_url, cookies=cookie_jar, extra_headers=extra_headers)
                    if not probe.get('ok'):
                        probe_mobile = self.probe_video_url(best, referer=mobile_url, cookies=cookie_jar, extra_headers=extra_headers)
                    else:
                        probe_mobile = None
                    return {
                        'success': True,
                        'url': post_url,
                        'mobile_url': mobile_url,
                        'video_url': best,
                        'probe': probe,
                        'probe_mobile': probe_mobile
                    }

            if not video_url:
                return {'success': False, 'error': 'Video no encontrado', 'url': post_url, 'video_url': None}

            return {'success': True, 'url': post_url, 'mobile_url': mobile_url, 'video_url': video_url}

        except Exception as e:
            logger.error(f"❌ Error scrapando video: {e}")
            return {'success': False, 'error': str(e), 'url': post_url, 'video_url': None}
    
    def scrape_page_posts(self, page_url: str, num_posts: int = 10) -> Dict:
        """
        Extrae múltiples posts de una página
        
        Args:
            page_url: URL de la página o nombre de la página
            num_posts: Número de posts a extraer
            
        Returns:
            Dict con lista de posts
        """
        if not self.driver:
            self.setup_driver()
        
        try:
            # Convertir a URL móvil
            if not page_url.startswith('http'):
                mobile_url = f"https://m.facebook.com/{page_url}"
            else:
                mobile_url = self.convert_to_mobile_url(page_url)
            
            logger.info(f"🔍 Accediendo a página: {mobile_url}")
            self.driver.get(mobile_url)
            time.sleep(3)
            
            # Scroll para cargar más posts
            posts_found = set()
            scroll_attempts = 0
            max_scrolls = num_posts // 2 + 2
            
            while len(posts_found) < num_posts and scroll_attempts < max_scrolls:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                scroll_attempts += 1
                
                # Buscar enlaces a posts
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                links = soup.find_all('a', href=True)
                
                for link in links:
                    href = link['href']
                    if '/posts/' in href or '/photo' in href:
                        # Construir URL completa
                        if href.startswith('/'):
                            full_url = f"https://m.facebook.com{href}"
                        else:
                            full_url = href
                        
                        # Limpiar URL
                        clean_url = full_url.split('?')[0]
                        posts_found.add(clean_url)
                        
                        if len(posts_found) >= num_posts:
                            break
            
            logger.info(f"📝 Encontrados {len(posts_found)} enlaces a posts")
            
            # Scrapear cada post
            posts_data = []
            for idx, post_url in enumerate(list(posts_found)[:num_posts]):
                logger.info(f"📥 Scrapeando post {idx + 1}/{num_posts}")
                try:
                    post_result = self.scrape_post_by_url(post_url)
                    if post_result['success']:
                        posts_data.append(post_result['post'])
                    time.sleep(2)  # Delay entre posts
                except Exception as e:
                    logger.warning(f"Error en post {post_url}: {e}")
                    continue
            
            return {
                'success': True,
                'page_url': page_url,
                'total_posts': len(posts_data),
                'posts': posts_data
            }
            
        except Exception as e:
            logger.error(f"❌ Error scrapeando página: {e}")
            return {
                'success': False,
                'error': str(e),
                'page_url': page_url,
                'posts': []
            }
    
    def close(self):
        """Cierra el navegador"""
        if self.driver:
            self.driver.quit()
            logger.info("🔒 Navegador cerrado")


# Singleton para reutilizar el scraper
_scraper_instance = None

def get_scraper_instance(headless: bool = True) -> FacebookSeleniumScraper:
    """Obtiene o crea una instancia del scraper"""
    global _scraper_instance
    if _scraper_instance is None:
        _scraper_instance = FacebookSeleniumScraper(headless=headless)
    return _scraper_instance

def close_scraper_instance():
    """Cierra la instancia del scraper"""
    global _scraper_instance
    if _scraper_instance:
        _scraper_instance.close()
        _scraper_instance = None
