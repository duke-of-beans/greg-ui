"""
title: Deep Dive
author: Fu-Jie
author_url: https://github.com/Fu-Jie/openwebui-extensions
funding_url: https://github.com/open-webui
version: 1.1.0
icon_url: data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwYXRoIGQ9Ik0xMiA3djE0Ii8+PHBhdGggZD0iTTMgMThhMSAxIDAgMCAxLTEtMVY0YTEgMSAwIDAgMSAxLTFoNWE0IDQgMCAwIDEgNCA0IDQgNCAwIDAgMSA0LTRoNWExIDEgMCAwIDEgMSAxdjEzYTEgMSAwIDAgMS0xIDFoLTZhMyAzIDAgMCAwLTMgMyAzIDMgMCAwIDAtMy0zeiIvPjxwYXRoIGQ9Ik02IDEyaDIiLz48cGF0aCBkPSJNMTYgMTJoMiIvPjwvc3ZnPg==
requirements: markdown
description: A comprehensive thinking lens that dives deep into any content - from context to logic, insights, and action paths.
"""

import asyncio
import json
import re
import logging
from typing import Optional, Dict, Any, Callable, Awaitable, List
from datetime import datetime

# Third-party imports
from pydantic import BaseModel, Field
from fastapi import Request
import markdown

# OpenWebUI imports
from open_webui.utils.chat import generate_chat_completion
from open_webui.models.users import Users

# Logging setup
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ── OpenWebUI version detection for async DB compatibility ──────────
try:
    from open_webui.env import VERSION as _owui_version
except ImportError:
    _owui_version = "0.0.0"


def _owui_version_ge(threshold: str) -> bool:
    try:
        v = [int(x) for x in _owui_version.split(".")[:3]]
        t = [int(x) for x in threshold.split(".")[:3]]
        return v >= t
    except (ValueError, TypeError):
        return False


async def _call_db(method, *args, **kwargs):
    if _owui_version_ge("0.9.0"):
        return await method(*args, **kwargs)
    else:
        return method(*args, **kwargs)

# =================================================================
# HTML Template - Process-Oriented Design with Theme Support
# =================================================================
HTML_WRAPPER_TEMPLATE = """
<!-- OPENWEBUI_PLUGIN_OUTPUT -->
<!DOCTYPE html>
<html lang="{user_language}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        :root {
            --dd-bg-primary: #ffffff;
            --dd-bg-secondary: #f8fafc;
            --dd-bg-tertiary: #f1f5f9;
            --dd-text-primary: #0f172a;
            --dd-text-secondary: #334155;
            --dd-text-dim: #64748b;
            --dd-border: #e2e8f0;
            --dd-accent: #3b82f6;
            --dd-accent-soft: #eff6ff;
            --dd-header-gradient: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            --dd-shadow: 0 10px 40px rgba(0,0,0,0.06);
            --dd-code-bg: #f1f5f9;
        }
        .theme-dark {
            --dd-bg-primary: #1e293b;
            --dd-bg-secondary: #0f172a;
            --dd-bg-tertiary: #334155;
            --dd-text-primary: #f1f5f9;
            --dd-text-secondary: #e2e8f0;
            --dd-text-dim: #94a3b8;
            --dd-border: #475569;
            --dd-accent: #60a5fa;
            --dd-accent-soft: rgba(59, 130, 246, 0.15);
            --dd-header-gradient: linear-gradient(135deg, #0f172a 0%, #1e1e2e 100%);
            --dd-shadow: 0 10px 40px rgba(0,0,0,0.3);
            --dd-code-bg: #334155;
        }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; 
            margin: 0; 
            padding: 10px; 
            background-color: transparent; 
        }
        #main-container { 
            display: flex; 
            flex-direction: column;
            gap: 24px; 
            width: 100%;
            max-width: 900px;
            margin: 0 auto;
        }
        .plugin-item { 
            background: var(--dd-bg-primary); 
            border-radius: 24px; 
            box-shadow: var(--dd-shadow); 
            overflow: hidden; 
            border: 1px solid var(--dd-border); 
        }
        /* STYLES_INSERTION_POINT */
    </style>
</head>
<body>
    <div id="main-container">
        <!-- CONTENT_INSERTION_POINT -->
    </div>
    <!-- SCRIPTS_INSERTION_POINT -->
    <script>
    (function() {
        const parseColorLuma = (colorStr) => {
            if (!colorStr) return null;
            let m = colorStr.match(/^#?([0-9a-f]{6})$/i);
            if (m) {
                const hex = m[1];
                const r = parseInt(hex.slice(0, 2), 16);
                const g = parseInt(hex.slice(2, 4), 16);
                const b = parseInt(hex.slice(4, 6), 16);
                return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
            }
            m = colorStr.match(/rgba?\\s*\\(\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*(\\d+)/i);
            if (m) {
                const r = parseInt(m[1], 10);
                const g = parseInt(m[2], 10);
                const b = parseInt(m[3], 10);
                return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
            }
            return null;
        };
        const getThemeFromMeta = (doc) => {
            const metas = Array.from((doc || document).querySelectorAll('meta[name="theme-color"]'));
            if (!metas.length) return null;
            const color = metas[metas.length - 1].content.trim();
            const luma = parseColorLuma(color);
            if (luma === null) return null;
            return luma < 0.5 ? 'dark' : 'light';
        };
        const getParentDocumentSafe = () => {
            try {
                if (!window.parent || window.parent === window) return null;
                const pDoc = window.parent.document;
                void pDoc.title;
                return pDoc;
            } catch (err) { return null; }
        };
        const getThemeFromParentClass = () => {
            try {
                if (!window.parent || window.parent === window) return null;
                const pDoc = window.parent.document;
                const html = pDoc.documentElement;
                const body = pDoc.body;
                const htmlClass = html ? html.className : '';
                const bodyClass = body ? body.className : '';
                const htmlDataTheme = html ? html.getAttribute('data-theme') : '';
                if (htmlDataTheme === 'dark' || bodyClass.includes('dark') || htmlClass.includes('dark')) return 'dark';
                if (htmlDataTheme === 'light' || bodyClass.includes('light') || htmlClass.includes('light')) return 'light';
                return null;
            } catch (err) { return null; }
        };
        const setTheme = () => {
            const parentDoc = getParentDocumentSafe();
            const metaTheme = parentDoc ? getThemeFromMeta(parentDoc) : null;
            const parentClassTheme = getThemeFromParentClass();
            const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
            const chosen = metaTheme || parentClassTheme || (prefersDark ? 'dark' : 'light');
            document.documentElement.classList.toggle('theme-dark', chosen === 'dark');
        };
        setTheme();
        if (window.matchMedia) {
            window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', setTheme);
        }
    })();
    </script>
</body>
</html>
"""

# =================================================================
# i18n - Multi-language Support
# =================================================================

TRANSLATIONS = {
    "en-US": {
        "title": "Deep Dive Analysis",
        "badge": "Thinking Process",
        "phase_01": "Phase 01",
        "phase_02": "Phase 02",
        "phase_03": "Phase 03",
        "phase_04": "Phase 04",
        "context_label": "The Context",
        "logic_label": "The Logic",
        "insight_label": "The Insight",
        "path_label": "The Path",
        "word_count_label": "words",
        "footer_engine": "Deep Dive Engine v1.1",
        "footer_tag": "AI-Powered",
        "status_analyzing": "🌊 Deep Dive: Analyzing Context & Logic...",
        "status_complete": "🌊 Deep Dive complete!",
        "notification_initiating": "🌊 Initiating Deep Dive thinking process...",
        "notification_complete": "🌊 Deep Dive complete, {user_name}! Thinking chain generated.",
        "error_brief": "Content too brief ({length} chars). Deep Dive requires at least {min_length} chars for meaningful analysis.",
        "no_context": "No context extracted.",
        "no_logic": "No logic deconstructed.",
        "no_insight": "No insights found.",
        "no_path": "No path defined.",
        "no_items": "No items found.",
    },
    "zh-CN": {
        "title": "精读分析报告",
        "badge": "思维过程",
        "phase_01": "第一阶段",
        "phase_02": "第二阶段",
        "phase_03": "第三阶段",
        "phase_04": "第四阶段",
        "context_label": "全景 (The Context)",
        "logic_label": "脉络 (The Logic)",
        "insight_label": "洞察 (The Insight)",
        "path_label": "路径 (The Path)",
        "word_count_label": "字",
        "footer_engine": "Deep Dive Engine v1.1",
        "footer_tag": "AI 驱动分析",
        "status_analyzing": "🌊 深度下潜：正在分析背景与逻辑...",
        "status_complete": "🌊 深度下潜完成！",
        "notification_initiating": "🌊 正在启动深度下潜思维链...",
        "notification_complete": "🌊 深度下潜完成，{user_name}！思维链已生成。",
        "error_brief": "内容太短（{length} 字符）。深度下潜需要至少 {min_length} 字符才能进行有意义的分析。",
        "no_context": "未能提取全景信息。",
        "no_logic": "未能解构脉络。",
        "no_insight": "未能发现洞察。",
        "no_path": "未能定义路径。",
        "no_items": "未找到条目。",
    },
    "zh-HK": {
        "title": "精讀分析報告",
        "badge": "思維過程",
        "phase_01": "第一階段",
        "phase_02": "第二階段",
        "phase_03": "第三階段",
        "phase_04": "第四階段",
        "context_label": "全景 (The Context)",
        "logic_label": "脈絡 (The Logic)",
        "insight_label": "洞察 (The Insight)",
        "path_label": "路徑 (The Path)",
        "word_count_label": "字",
        "footer_engine": "Deep Dive Engine v1.1",
        "footer_tag": "AI 驅動分析",
        "status_analyzing": "🌊 深度下潛：正在分析背景與邏輯...",
        "status_complete": "🌊 深度下潛完成！",
        "notification_initiating": "🌊 正在啟動深度下潛思維鏈...",
        "notification_complete": "🌊 深度下潛完成，{user_name}！思維鏈已生成。",
        "error_brief": "內容太短（{length} 字符）。深度下潛需要至少 {min_length} 字符才能進行有意義的分析。",
        "no_context": "未能提取全景資訊。",
        "no_logic": "未能解構脈絡。",
        "no_insight": "未能發現洞察。",
        "no_path": "未能定義路徑。",
        "no_items": "未找到條目。",
    },
    "zh-TW": {
        "title": "精讀分析報告",
        "badge": "思維過程",
        "phase_01": "第一階段",
        "phase_02": "第二階段",
        "phase_03": "第三階段",
        "phase_04": "第四階段",
        "context_label": "全景 (The Context)",
        "logic_label": "脈絡 (The Logic)",
        "insight_label": "洞察 (The Insight)",
        "path_label": "路徑 (The Path)",
        "word_count_label": "字",
        "footer_engine": "Deep Dive Engine v1.1",
        "footer_tag": "AI 驅動分析",
        "status_analyzing": "🌊 深度下潛：正在分析背景與邏輯...",
        "status_complete": "🌊 深度下潛完成！",
        "notification_initiating": "🌊 正在啟動深度下潛思維鏈...",
        "notification_complete": "🌊 深度下潛完成，{user_name}！思維鏈已生成。",
        "error_brief": "內容太短（{length} 字符）。深度下潛需要至少 {min_length} 字符才能進行有意義的分析。",
        "no_context": "未能提取全景資訊。",
        "no_logic": "未能解構脈絡。",
        "no_insight": "未能發現洞察。",
        "no_path": "未能定義路徑。",
        "no_items": "未找到條目。",
    },
    "ja-JP": {
        "title": "ディープダイブ分析レポート",
        "badge": "思考プロセス",
        "phase_01": "フェーズ 01",
        "phase_02": "フェーズ 02",
        "phase_03": "フェーズ 03",
        "phase_04": "フェーズ 04",
        "context_label": "コンテキスト (The Context)",
        "logic_label": "ロジック (The Logic)",
        "insight_label": "インサイト (The Insight)",
        "path_label": "パス (The Path)",
        "word_count_label": "文字",
        "footer_engine": "Deep Dive Engine v1.1",
        "footer_tag": "AI駆動分析",
        "status_analyzing": "🌊 ディープダイブ：コンテキストとロジックを分析中...",
        "status_complete": "🌊 ディープダイブ完了！",
        "notification_initiating": "🌊 ディープダイブ思考プロセスを開始しています...",
        "notification_complete": "🌊 ディープダイブ完了、{user_name}さん！思考チェーンが生成されました。",
        "error_brief": "内容が短すぎます（{length}文字）。ディープダイブには最低{min_length}文字が必要です。",
        "no_context": "コンテキストが抽出されませんでした。",
        "no_logic": "ロジックが分解されませんでした。",
        "no_insight": "インサイトが見つかりませんでした。",
        "no_path": "パスが定義されませんでした。",
        "no_items": "項目が見つかりませんでした。",
    },
    "ko-KR": {
        "title": "심층 분석 보고서",
        "badge": "사고 과정",
        "phase_01": "단계 01",
        "phase_02": "단계 02",
        "phase_03": "단계 03",
        "phase_04": "단계 04",
        "context_label": "컨텍스트 (The Context)",
        "logic_label": "로직 (The Logic)",
        "insight_label": "통찰 (The Insight)",
        "path_label": "경로 (The Path)",
        "word_count_label": "단어",
        "footer_engine": "Deep Dive Engine v1.1",
        "footer_tag": "AI 기반 분석",
        "status_analyzing": "🌊 심층 분석: 컨텍스트 및 로직 분석 중...",
        "status_complete": "🌊 심층 분석 완료!",
        "notification_initiating": "🌊 심층 분석 사고 과정을 시작합니다...",
        "notification_complete": "🌊 심층 분석 완료, {user_name}님! 사고 체인이 생성되었습니다.",
        "error_brief": "내용이 너무 짧습니다 ({length}자). 심층 분석을 위해서는 최소 {min_length}자가 필요합니다.",
        "no_context": "컨텍스트가 추출되지 않았습니다.",
        "no_logic": "로직이 분석되지 않았습니다.",
        "no_insight": "통찰을 찾을 수 없습니다.",
        "no_path": "경로가 정의되지 않았습니다.",
        "no_items": "항목을 찾을 수 없습니다.",
    },
    "fr-FR": {
        "title": "Rapport d'Analyse Approfondie",
        "badge": "Processus de Réflexion",
        "phase_01": "Phase 01",
        "phase_02": "Phase 02",
        "phase_03": "Phase 03",
        "phase_04": "Phase 04",
        "context_label": "Le Contexte",
        "logic_label": "La Logique",
        "insight_label": "L'Aperçu",
        "path_label": "Le Chemin",
        "word_count_label": "mots",
        "footer_engine": "Deep Dive Engine v1.1",
        "footer_tag": "Propulsé par l'IA",
        "status_analyzing": "🌊 Deep Dive : Analyse du contexte et de la logique...",
        "status_complete": "🌊 Deep Dive terminé !",
        "notification_initiating": "🌊 Initialisation du processus de réflexion Deep Dive...",
        "notification_complete": "🌊 Deep Dive terminé, {user_name} ! Chaîne de réflexion générée.",
        "error_brief": "Contenu trop court ({length} caractères). Deep Dive nécessite au moins {min_length} caractères.",
        "no_context": "Aucun contexte extrait.",
        "no_logic": "Aucune logique déconstruite.",
        "no_insight": "Aucun aperçu trouvé.",
        "no_path": "Aucun chemin défini.",
        "no_items": "Aucun élément trouvé.",
    },
    "de-DE": {
        "title": "Tiefenanalyse-Bericht",
        "badge": "Denkprozess",
        "phase_01": "Phase 01",
        "phase_02": "Phase 02",
        "phase_03": "Phase 03",
        "phase_04": "Phase 04",
        "context_label": "Der Kontext",
        "logic_label": "Die Logik",
        "insight_label": "Die Erkenntnis",
        "path_label": "Der Pfad",
        "word_count_label": "Wörter",
        "footer_engine": "Deep Dive Engine v1.1",
        "footer_tag": "KI-gestützt",
        "status_analyzing": "🌊 Deep Dive: Kontext und Logik werden analysiert...",
        "status_complete": "🌊 Deep Dive abgeschlossen!",
        "notification_initiating": "🌊 Deep Dive Denkprozess wird eingeleitet...",
        "notification_complete": "🌊 Deep Dive abgeschlossen, {user_name}! Denkprozess wurde generiert.",
        "error_brief": "Inhalt zu kurz ({length} Zeichen). Deep Dive erfordert mindestens {min_length} Zeichen.",
        "no_context": "Kein Kontext extrahiert.",
        "no_logic": "Keine Logik dekonstruiert.",
        "no_insight": "Keine Erkenntnisse gefunden.",
        "no_path": "Kein Pfad definiert.",
        "no_items": "Keine Elemente gefunden.",
    },
    "es-ES": {
        "title": "Informe de Análisis Profundo",
        "badge": "Proceso de Pensamiento",
        "phase_01": "Fase 01",
        "phase_02": "Fase 02",
        "phase_03": "Fase 03",
        "phase_04": "Fase 04",
        "context_label": "El Contexto",
        "logic_label": "La Lógica",
        "insight_label": "La Perspicacia",
        "path_label": "El Camino",
        "word_count_label": "palabras",
        "footer_engine": "Deep Dive Engine v1.1",
        "footer_tag": "Potenciado por IA",
        "status_analyzing": "🌊 Deep Dive: Analizando contexto y lógica...",
        "status_complete": "🌊 Deep Dive completado!",
        "notification_initiating": "🌊 Iniciando el proceso de pensamiento Deep Dive...",
        "notification_complete": "🌊 Deep Dive completado, {user_name}! Cadena de pensamiento generada.",
        "error_brief": "Contenido demasiado breve ({length} caracteres). Deep Dive requiere al menos {min_length} caracteres.",
        "no_context": "No se extrajo contexto.",
        "no_logic": "No se deconstruyó la lógica.",
        "no_insight": "No se encontraron perspicacias.",
        "no_path": "No se definió el camino.",
        "no_items": "No se encontraron elementos.",
    },
    "it-IT": {
        "title": "Rapporto di Analisi Approfondita",
        "badge": "Processo di Pensiero",
        "phase_01": "Fase 01",
        "phase_02": "Fase 02",
        "phase_03": "Fase 03",
        "phase_04": "Fase 04",
        "context_label": "Il Contesto",
        "logic_label": "La Logica",
        "insight_label": "L'Intuizione",
        "path_label": "Il Percorso",
        "word_count_label": "parole",
        "footer_engine": "Deep Dive Engine v1.1",
        "footer_tag": "Basato su IA",
        "status_analyzing": "🌊 Deep Dive: Analisi del contesto e della logica...",
        "status_complete": "🌊 Deep Dive completato!",
        "notification_initiating": "🌊 Avvio del processo di pensiero Deep Dive...",
        "notification_complete": "🌊 Deep Dive completato, {user_name}! Catena di pensiero generata.",
        "error_brief": "Contenuto troppo breve ({length} caratteri). Deep Dive richiede almeno {min_length} caratteri.",
        "no_context": "Nessun contesto estratto.",
        "no_logic": "Nessuna logica decostruita.",
        "no_insight": "Nessuna intuizione trovata.",
        "no_path": "Nessun percorso definito.",
        "no_items": "Nessun elemento trovato.",
    },
    "vi-VN": {
        "title": "Báo Cáo Phân Tích Chuyên Sâu",
        "badge": "Quy Trình Tư Duy",
        "phase_01": "Giai đoạn 01",
        "phase_02": "Giai đoạn 02",
        "phase_03": "Giai đoạn 03",
        "phase_04": "Giai đoạn 04",
        "context_label": "Bối Cảnh",
        "logic_label": "Logic",
        "insight_label": "Thông Tin Chuyên Sâu",
        "path_label": "Lộ Trình",
        "word_count_label": "từ",
        "footer_engine": "Deep Dive Engine v1.1",
        "footer_tag": "Được hỗ trợ bởi AI",
        "status_analyzing": "🌊 Deep Dive: Đang phân tích bối cảnh và logic...",
        "status_complete": "🌊 Deep Dive hoàn tất!",
        "notification_initiating": "🌊 Đang khởi tạo quy trình tư duy Deep Dive...",
        "notification_complete": "🌊 Deep Dive hoàn tất, {user_name}! Chuỗi tư duy đã được tạo.",
        "error_brief": "Nội dung quá ngắn ({length} ký tự). Deep Dive cần ít nhất {min_length} ký tự.",
        "no_context": "Không có bối cảnh nào được trích xuất.",
        "no_logic": "Không có logic nào được phân tích.",
        "no_insight": "Không tìm thấy thông tin chuyên sâu nào.",
        "no_path": "Không có lộ trình nào được xác định.",
        "no_items": "Không tìm thấy mục nào.",
    },
    "id-ID": {
        "title": "Laporan Analisis Mendalam",
        "badge": "Proses Berpikir",
        "phase_01": "Fase 01",
        "phase_02": "Fase 02",
        "phase_03": "Fase 03",
        "phase_04": "Fase 04",
        "context_label": "Konteks",
        "logic_label": "Logika",
        "insight_label": "Wawasan",
        "path_label": "Jalur",
        "word_count_label": "kata",
        "footer_engine": "Deep Dive Engine v1.1",
        "footer_tag": "Didukung AI",
        "status_analyzing": "🌊 Deep Dive: Menganalisis konteks & logika...",
        "status_complete": "🌊 Deep Dive selesai!",
        "notification_initiating": "🌊 Memulai proses berpikir Deep Dive...",
        "notification_complete": "🌊 Deep Dive selesai, {user_name}! Rantai pemikiran dihasilkan.",
        "error_brief": "Konten terlalu singkat ({length} karakter). Deep Dive memerlukan setidaknya {min_length} karakter.",
        "no_context": "Tidak ada konteks yang diekstraksi.",
        "no_logic": "Tidak ada logika yang didekonstruksi.",
        "no_insight": "Tidak ada wawasan yang ditemukan.",
        "no_path": "Tidak ada jalur yang ditentukan.",
        "no_items": "Tidak ada item yang ditemukan.",
    },
}

# Supported language fallbacks
LANGUAGE_FALLBACKS = {
    "zh-HK": "zh-HK",
    "zh-TW": "zh-TW",
    "zh-MO": "zh-HK",
    "en-GB": "en-US",
    "en-AU": "en-US",
    "en-CA": "en-US",
    "es-MX": "es-ES",
    "es-AR": "es-ES",
    "fr-CA": "fr-FR",
    "fr-BE": "fr-FR",
    "fr-CH": "fr-FR",
    "de-AT": "de-DE",
    "de-CH": "de-DE",
    "vi-VN": "vi-VN",
    "id-ID": "id-ID",
}

PROMPTS = {
    "en-US": {
        "system": """You are a Deep Dive Analyst. Your goal is to guide the user through a comprehensive thinking process, moving from surface understanding to deep strategic action.

## Output Format (STRICT)
You MUST return ONLY a JSON object. Do not include any markdown headings, greetings, or meta-commentary.
The JSON structure MUST be:
{
  "context": "String (2-3 paragraphs high-level panoramic view)",
  "logic": [
    {"title": "Short Keyword", "content": "Detailed deconstruction of reasoning/assumptions"}
  ],
  "insight": [
    {"title": "Short Keyword", "content": "The non-obvious value or 'Aha!' moment"}
  ],
  "path": [
    {"title": "Next Step", "content": "Specific, actionable application of this knowledge"}
  ]
}

## Thinking Dimensions
- **Context**: Panoramic view of the situation/problem.
- **Logic**: Underlying reasoning and mental models.
- **Insight**: Deep implications and blind spots.
- **Path**: Prioritized next steps.

## Rules
- Output content in the exact language specified by the user.
- Maintain a professional, analytical, yet inspiring tone.
- Ensure 'title' fields are brief (1-4 words) and 'content' is substantial.""",
        "user": """Initiate a Deep Dive into the following content:

**User Context:**
- User: {user_name}
- Time: {current_date_time_str}
- Language: {user_language}

**Content to Analyze:**
```
{long_text_content}
```

Return the full thinking chain in JSON format: Context → Logic → Insight → Path.""",
    },
    "zh-CN": {
        "system": """你是一位“深度下潜 (Deep Dive)”分析专家。你的目标是引导用户完成一个全面的思维过程，从表面理解深入到战略行动。

## 输出格式 (严格遵守)
你必须【仅】返回一个 JSON 对象。不要包含任何 Markdown 标题、寒暄或元对话。
JSON 结构必须如下：
{
  "context": "字符串（2-3 段话的全景视图）",
  "logic": [
    {"title": "短关键词", "content": "对推理/假设的详细解构"}
  ],
  "insight": [
    {"title": "短关键词", "content": "非显性价值或“原来如此”的时刻"}
  ],
  "path": [
    {"title": "下一步行动", "content": "对该知识的具体、可执行的应用"}
  ]
}

## 思维维度
- **全景 (Context)**: 情境/问题的全景视图。
- **脉络 (Logic)**: 底层推理和思维模型。
- **洞察 (Insight)**: 深层含义和盲点。
- **路径 (Path)**: 优先级排序的下一步行动。

## 规则
- 使用用户指定的语言输出内容。
- 保持专业、分析性且富有启发性的语调。
- 确保 "title" 字段简短（1-4 个字），"content" 内容充实。""",
        "user": """对以下内容发起“深度下潜”：

**用户上下文：**
- 用户：{user_name}
- 时间：{current_date_time_str}
- 语言：{user_language}

**待分析内容：**
```
{long_text_content}
```

请以 JSON 格式执行完整的思维链：全景 (Context) → 脉络 (Logic) → 洞察 (Insight) → 路径 (Path)。""",
    },
    "zh-HK": {
        "system": """你是一位「深度下潛 (Deep Dive)」分析專家。你的目標是引導用戶完成一個全面的思維過程，從表面理解深入到戰略行動。

## 輸出格式 (嚴格遵守)
你必須【僅】返回一個 JSON 對象。不要包含任何 Markdown 標題、寒暄或元對話。
JSON 結構必須如下：
{
  "context": "字符串（2-3 段話的全景視圖）",
  "logic": [
    {"title": "短關鍵詞", "content": "對推理/假設的詳細解構"}
  ],
  "insight": [
    {"title": "短關鍵詞", "content": "非顯性價值或「原來如此」的時刻"}
  ],
  "path": [
    {"title": "下一步行動", "content": "對該知識的具體、可執行之應用"}
  ]
}

## 思維維度
- **全景 (Context)**: 情境/問題的全景視圖。
- **脈絡 (Logic)**: 底層推理和思維模型。
- **洞察 (Insight)**: 深層含義和盲點。
- **路徑 (Path)**: 優先級排序的下一步行動。

## 規則
- 使用用戶指定的語言輸出內容。
- 保持專業、分析性且富有啟發性的語調。
- 確保 "title" 字段簡短（1-4 個字），"content" 內容充實。""",
        "user": """對以下內容發起「深度下潛」：

**用戶上下文：**
- 用戶：{user_name}
- 時間：{current_date_time_str}
- 語言：{user_language}

**待分析內容：**
```
{long_text_content}
```

請以 JSON 格式執行完整的思維鏈：全景 (Context) → 脈絡 (Logic) → 洞察 (Insight) → 路徑 (Path)。""",
    },
    "zh-TW": {
        "system": """你是一位「深度下潛 (Deep Dive)」分析專家。你的目標是引導用戶完成一個全面的思維過程，從表面理解深入到戰略行動。

## 輸出格式 (嚴格遵守)
你必須【僅】返回一個 JSON 對象。不要包含任何 Markdown 標題、寒暄或元對話。
JSON 結構必須如下：
{
  "context": "字符串（2-3 段話的全景視圖）",
  "logic": [
    {"title": "短關鍵詞", "content": "對推理/假設的詳細解構"}
  ],
  "insight": [
    {"title": "短關鍵詞", "content": "非顯性價值或「原來如此」的時刻"}
  ],
  "path": [
    {"title": "下一步行動", "content": "對該知識的具體、可執行之應用"}
  ]
}

## 思維維度
- **全景 (Context)**: 情境/問題的全景視圖。
- **脈絡 (Logic)**: 底層推理和思維模型。
- **洞察 (Insight)**: 深層含義和盲點。
- **路徑 (Path)**: 優先級排序的下一步行動。

## 規則
- 使用用戶指定的語言輸出內容。
- 保持專業、分析性且富有啟發性的語調。
- 確保 "title" 字段簡短（1-4 個字），"content" 內容充實。""",
        "user": """對以下內容發起「深度下潛」：

**用戶上下文：**
- 用戶：{user_name}
- 時間：{current_date_time_str}
- 語言：{user_language}

**待分析內容：**
```
{long_text_content}
```

請以 JSON 格式執行完整的思維鏈：全景 (Context) → 脈絡 (Logic) → 洞察 (Insight) → 路徑 (Path)。""",
    },
    "ja-JP": {
        "system": """あなたは「ディープダイブ (Deep Dive)」分析のエキスパートです。あなたの目標は、表面的な理解から深い戦略的行動へと、包括的な思考プロセスを通じてユーザーを導くことです。

## 出力形式 (厳守)
あなたは JSON オブジェクト【のみ】を返す必要があります。Markdown の見出し、挨拶、メタコメントは含めないでください。
JSON 構造は以下の通りである必要があります：
{
  "context": "文字列 (2〜3 段落のハイレベルなパノラマビュー)",
  "logic": [
    {"title": "短いキーワード", "content": "推論/仮定の詳細な解体"}
  ],
  "insight": [
    {"title": "短いキーワード", "content": "非明示的な価値、または「なるほど！」という瞬間"}
  ],
  "path": [
    {"title": "次のステップ", "content": "この知識の具体的かつ実行可能な適用"}
  ]
}

## 思考の次元
- **コンテキスト (Context)**: 状況/問題のパノラマビュー。
- **ロジック (Logic)**: 基礎となる推論と思考モデル。
- **インサイト (Insight)**: 深い含意と盲点。
- **パス (Path)**: 優先順位付けされた次のステップ。

## ルール
- ユーザーが指定した言語で内容を出力してください。
- 専門的で分析的、かつ刺激的なトーンを維持してください。
- "title" フィールドは簡潔（1〜4語）にし、"content" 内容を充実させてください。""",
        "user": """以下の内容に対して「ディープダイブ」を開始します：

**ユーザーコンテキスト：**
- ユーザー：{user_name}
- 日時：{current_date_time_str}
- 言語：{user_language}

**分析対象コンテンツ：**
```
{long_text_content}
```

JSON 形式で完全な思考チェーンを実行してください：コンテキスト (Context) → ロジック (Logic) → インサイト (Insight) → パス (Path)。""",
    },
    "ko-KR": {
        "system": """귀하는 '심층 분석 (Deep Dive)' 전문가입니다. 귀하의 목표는 사용자를 표면적인 이해에서 깊은 전략적 행동으로 이끄는 포괄적인 사고 과정을 안내하는 것입니다.

## 출력 형식 (엄격 준수)
반드시 JSON 객체【만】 반환해야 합니다. Markdown 제목, 인사말 또는 메타 코멘트를 포함하지 마십시오.
JSON 구조는 다음과 같아야 합니다:
{
  "context": "문자열 (2-3문단의 고차원적인 파노라마 뷰)",
  "logic": [
    {"title": "짧은 키워드", "content": "추론/가정에 대한 상세한 해체"}
  ],
  "insight": [
    {"title": "짧은 키워드", "content": "비명시적인 가치 또는 '아하!' 하는 순간"}
  ],
  "path": [
    {"title": "다음 단계", "content": "이 지식에 대한 구체적이고 실행 가능한 적용"}
  ]
}

## 사고 차원
- **컨텍스트 (Context)**: 상황/문제에 대한 파노라마 뷰.
- **로직 (Logic)**: 기저의 추론 및 사고 모델.
- **통찰 (Insight)**: 깊은 함의 및 사각지대.
- **경로 (Path)**: 우선순위가 지정된 다음 단계.

## 규칙
- 사용자가 지정한 언어로 내용을 출력하십시오.
- 전문적이고 분석적이며 고무적인 어조를 유지하십시오.
- "title" 필드는 간결하게(1-4단어) 작성하고, "content" 내용은 충실하게 작성하십시오.""",
        "user": """다음 내용에 대해 '심층 분석'을 시작합니다:

**사용자 컨텍스트:**
- 사용자: {user_name}
- 시간: {current_date_time_str}
- 언어: {user_language}

**분석할 내용:**
```
{long_text_content}
```

전체 사고 체인을 JSON 형식으로 실행하십시오: 컨텍스트 (Context) → 로직 (Logic) → 통찰 (Insight) → 경로 (Path).""",
    },
    "fr-FR": {
        "system": """Vous êtes un expert en « Analyse Approfondie (Deep Dive) ». Votre objectif est de guider l'utilisateur à travers un processus de réflexion complet, passant d'une compréhension superficielle à une action stratégique profonde.

## Format de Sortie (STRICT)
Vous DEVEZ retourner UNIQUEMENT un objet JSON. N'incluez pas de titres Markdown, de salutations ou de méta-commentaires.
La structure JSON DOIT être :
{
  "context": "Chaîne de caractères (vue panoramique de haut niveau en 2-3 paragraphes)",
  "logic": [
    {"title": "Mot-clé court", "content": "Déconstruction détaillée des raisonnements/hypothèses"}
  ],
  "insight": [
    {"title": "Mot-clé court", "content": "La valeur non évidente ou le moment « Eurêka ! »"}
  ],
  "path": [
    {"title": "Prochaine étape", "content": "Application spécifique et exploitable de ces connaissances"}
  ]
}

## Dimensions de Réflexion
- **Contexte (Context)** : Vue panoramique de la situation/problème.
- **Logique (Logic)** : Raisonnement sous-jacent et modèles mentaux.
- **Aperçu (Insight)** : Implications profondes et angles morts.
- **Chemin (Path)** : Prochaines étapes priorisées.

## Règles
- Produisez le contenu dans la langue exacte spécifiée par l'utilisateur.
- Maintenez un ton professionnel, analytique et inspirant.
- Assurez-vous que les champs « title » sont brefs (1-4 mots) et que le « content » est substantiel.""",
        "user": """Initiez une analyse approfondie sur le contenu suivant :

**Contexte utilisateur :**
- Utilisateur : {user_name}
- Temps : {current_date_time_str}
- Langue : {user_language}

**Contenu à analyser :**
```
{long_text_content}
```

Veuillez exécuter la chaîne de réflexion complète au format JSON : Contexte → Logique → Aperçu → Chemin.""",
    },
    "de-DE": {
        "system": """Sie sind ein Experte für „Tiefenanalyse (Deep Dive)“. Ihr Ziel ist es, den Benutzer durch einen umfassenden Denkprozess zu führen, der von oberflächlichem Verständnis zu tiefgreifendem strategischem Handeln führt.

## Ausgabeformat (STRIKT)
Sie MÜSSEN NUR ein JSON-Objekt zurückgeben. Fügen Sie keine Markdown-Überschriften, Begrüßungen oder Meta-Kommentare hinzu.
Die JSON-Struktur MUSS wie folgt aussehen:
{
  "context": "String (2-3 Absätze umfassender Überblick)",
  "logic": [
    {"title": "Kurzes Schlagwort", "content": "Detaillierte Dekonstruktion von Argumenten/Annahmen"}
  ],
  "insight": [
    {"title": "Kurzes Schlagwort", "content": "Der nicht offensichtliche Wert oder der „Aha-Moment“"}
  ],
  "path": [
    {"title": "Nächster Schritt", "content": "Spezifische, umsetzbare Anwendung dieses Wissens"}
  ]
}

## Denkdimensionen
- **Kontext (Context)**: Panoramablick auf die Situation/das Problem.
- **Logik (Logic)**: Zugrunde liegende Argumentation und Denkmodelle.
- **Erkenntnis (Insight)**: Tiefe Implikationen und blinde Flecken.
- **Pfad (Path)**: Priorisierte nächste Schritte.

## Regeln
- Ausgabe in der vom Benutzer angegebenen Sprache.
- Behalten Sie einen professionellen, analytischen und dennoch inspirierenden Ton bei.
- Stellen Sie sicher, dass die „title“-Felder kurz sind (1-4 Wörter) und der „content“ substanziell ist.""",
        "user": """Leiten Sie eine Tiefenanalyse für den folgenden Inhalt ein:

**Benutzerkontext:**
- Benutzer: {user_name}
- Zeit: {current_date_time_str}
- Sprache: {user_language}

**Zu analysierender Inhalt:**
```
{long_text_content}
```

Bitte führen Sie die vollständige Denkkette im JSON-Format aus: Kontext → Logik → Erkenntnis → Pfad.""",
    },
    "es-ES": {
        "system": """Usted es un experto en "Análisis Profundo (Deep Dive)". Su objetivo es guiar al usuario a través de un proceso de pensamiento integral, pasando de una comprensión superficial a una acción estratégica profunda.

## Formato de Salida (ESTRICTO)
DEBE devolver ÚNICAMENTE un objeto JSON. No incluya encabezados Markdown, saludos ni metacomentarios.
La estructura JSON DEBE ser:
{
  "context": "Cadena (vista panorámica de alto nivel en 2-3 párrafos)",
  "logic": [
    {"title": "Palabra clave corta", "content": "Deconstrucción detallada de razonamientos/suposiciones"}
  ],
  "insight": [
    {"title": "Palabra clave corta", "content": "El valor no evidente o el momento de revelación"}
  ],
  "path": [
    {"title": "Siguiente paso", "content": "Aplicación específica y accionable de este conocimiento"}
  ]
}

## Dimensiones de Pensamiento
- **Contexto (Context)**: Vista panorámica de la situación/problema.
- **Lógica (Logic)**: Razonamiento subyacente y modelos mentales.
- **Perspicacia (Insight)**: Implicaciones profundas y puntos ciegos.
- **Camino (Path)**: Siguientes pasos priorizados.

## Reglas
- Genere el contenido en el idioma exacto especificado por el usuario.
- Mantenga un tono profesional, analítico e inspirador.
- Asegúrese de que los campos "title" sean breves (1-4 palabras) y que el "content" sea sustancial.""",
        "user": """Inicie un Análisis Profundo sobre el siguiente contenido:

**Contexto del usuario:**
- Usuario: {user_name}
- Tiempo: {current_date_time_str}
- Idioma: {user_language}

**Contenido a analizar:**
```
{long_text_content}
```

Por favor, ejecute la cadena de pensamiento completa en formato JSON: Contexto → Lógica → Perspicacia → Camino.""",
    },
    "it-IT": {
        "system": """Sei un esperto di "Analisi Approfondita (Deep Dive)". Il tuo obiettivo è guidare l'utente attraverso un processo di pensiero completo, passando dalla comprensione superficiale all'azione strategica profonda.

## Formato di Output (RIGOROSO)
Devi restituire SOLTANTO un oggetto JSON. Non includere intestazioni Markdown, saluti o meta-commenti.
La struttura JSON DEVE essere:
{
  "context": "Stringa (2-3 paragrafi, visione panoramica di alto livello)",
  "logic": [
    {"title": "Breve parola chiave", "content": "De-costruzione dettagliata di ragionamenti/assunzioni"}
  ],
  "insight": [
    {"title": "Breve parola chiave", "content": "Il valore non ovvio o il momento 'Eureka!'"}
  ],
  "path": [
    {"title": "Passaggio successivo", "content": "Applicazione specifica e attuabile di questa conoscenza"}
  ]
}

## Dimensioni del Pensiero
- **Contesto (Context)**: Visione panoramica della situazione/problema.
- **Logica (Logic)**: Ragionamento sottostante e modelli mentali.
- **Intuizione (Insight)**: Implicazioni profonde e punti ciechi.
- **Percorso (Path)**: Passaggi successivi prioritari.

## Regole
- Genera il contenuto nella lingua esatta specificata dall'utente.
- Mantieni un tono professionale, analitico e stimolante.
- Assicurati che i campi 'title' siano brevi (1-4 parole) e che 'content' sia sostanzioso.""",
        "user": """Avvia un'Analisi Approfondita sul seguente contenuto:

**Contesto utente:**
- Utente: {user_name}
- Tempo: {current_date_time_str}
- Lingua: {user_language}

**Contenuto da analizzare:**
```
{long_text_content}
```

Restituisci la catena di pensiero completa in formato JSON: Contesto → Logica → Intuizione → Percorso.""",
    },
    "vi-VN": {
        "system": """Bạn là chuyên gia "Phân tích chuyên sâu (Deep Dive)". Mục tiêu của bạn là hướng dẫn người dùng thực hiện một quy trình tư duy toàn diện, đi từ hiểu biết bề mặt đến hành động chiến lược sâu sắc.

## Định dạng đầu ra (NGHIÊM NGẶT)
Bạn CHỈ được trả về một đối tượng JSON. Không bao gồm bất kỳ tiêu đề Markdown, lời chào hoặc nhận xét nào.
Cấu trúc JSON PHẢI là:
{
  "context": "Chuỗi (2-3 đoạn văn nhìn toàn cảnh cấp cao)",
  "logic": [
    {"title": "Từ khóa ngắn", "content": "Phân tích chi tiết về lập luận/giả định"}
  ],
  "insight": [
    {"title": "Từ khóa ngắn", "content": "Giá trị không hiển nhiên hoặc khoảnh khắc 'Aha!'"}
  ],
  "path": [
    {"title": "Bước tiếp theo", "content": "Ứng dụng cụ thể, có thể thực hiện được của kiến thức này"}
  ]
}

## Các chiều kích tư duy
- **Bối cảnh (Context)**: Cái nhìn toàn cảnh về tình huống/vấn đề.
- **Logic**: Lý luận cơ bản và các mô hình tư duy.
- **Thông tin chuyên sâu (Insight)**: Các hàm ý sâu sắc và điểm mù.
- **Lộ trình (Path)**: Các bước tiếp theo được ưu tiên.

## Quy tắc
- Xuất nội dung bằng chính xác ngôn ngữ mà người dùng chỉ định.
- Duy trì giọng điệu chuyên nghiệp, phân tích nhưng vẫn đầy cảm hứng.
- Đảm bảo các trường 'title' ngắn gọn (1-4 từ) và 'content' có nội dung phong phú.""",
        "user": """Bắt đầu Phân tích chuyên sâu về nội dung sau:

**Bối cảnh người dùng:**
- Người dùng: {user_name}
- Thời gian: {current_date_time_str}
- Ngôn ngữ: {user_language}

**Nội dung cần phân tích:**
```
{long_text_content}
```

Trả về chuỗi tư duy đầy đủ ở định dạng JSON: Bối cảnh → Logic → Thông tin chuyên sâu → Lộ trình.""",
    },
    "id-ID": {
        "system": """Anda adalah pakar "Analisis Mendalam (Deep Dive)". Tujuan Anda adalah membimbing pengguna melalui proses berpikir yang komprehensif, beralih dari pemahaman permukaan ke tindakan strategis yang mendalam.

## Format Output (KETAT)
Anda HARUS hanya mengembalikan objek JSON. Jangan sertakan judul Markdown, salam, atau komentar meta apa pun.
Struktur JSON HARUS:
{
  "context": "String (2-3 paragraf pandangan panorama tingkat tinggi)",
  "logic": [
    {"title": "Kata Kunci Pendek", "content": "Dekonstruksi mendalam tentang penalaran/asumsi"}
  ],
  "insight": [
    {"title": "Kata Kunci Pendek", "content": "Nilai yang tidak jelas atau momen 'Aha!'"}
  ],
  "path": [
    {"title": "Langkah Selanjutnya", "content": "Penerapan spesifik dan dapat ditindaklanjuti dari pengetahuan ini"}
  ]
}

## Dimensi Berpikir
- **Konteks (Context)**: Pandangan panorama dari situasi/masalah.
- **Logika (Logic)**: Penalaran dasar dan model mental.
- **Wawasan (Insight)**: Implikasi mendalam dan titik buta.
- **Jalur (Path)**: Langkah selanjutnya yang diprioritaskan.

## Aturan
- Hasilkan konten dalam bahasa yang tepat yang ditentukan oleh pengguna.
- Pertahankan nada profesional, analitis, namun tetap inspiratif.
- Pastikan bidang 'title' singkat (1-4 kata) dan 'content' substansial.""",
        "user": """Mulai Analisis Mendalam pada konten berikut:

**Konteks Pengguna:**
- Pengguna: {user_name}
- Waktu: {current_date_time_str}
- Bahasa: {user_language}

**Konten untuk Dianalisis:**
```
{long_text_content}
```

Kembalikan rantai pemikiran lengkap dalam format JSON: Konteks → Logika → Wawasan → Jalur.""",
    },
}

# =================================================================
# Premium CSS Design - Deep Dive Theme
# =================================================================

CSS_TEMPLATE = """
        .deep-dive {
            font-family: 'Inter', -apple-system, system-ui, sans-serif;
            color: var(--dd-text-secondary);
        }

        .dd-header {
            background: var(--dd-header-gradient);
            padding: 40px 32px;
            color: white;
            position: relative;
        }

        .dd-header-badge {
            display: inline-block;
            padding: 4px 12px;
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 100px;
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            margin-bottom: 16px;
        }

        .dd-title {
            font-size: 2rem;
            font-weight: 800;
            margin: 0 0 12px 0;
            letter-spacing: -0.02em;
        }

        .dd-meta {
            display: flex;
            gap: 20px;
            font-size: 0.85rem;
            opacity: 0.7;
        }

        .dd-body {
            padding: 32px;
            display: flex;
            flex-direction: column;
            gap: 40px;
            position: relative;
            background: var(--dd-bg-primary);
        }

        /* The Thinking Line */
        .dd-body::before {
            content: '';
            position: absolute;
            left: 52px;
            top: 40px;
            bottom: 40px;
            width: 2px;
            background: var(--dd-border);
            z-index: 0;
        }

        .dd-step {
            position: relative;
            z-index: 1;
            display: flex;
            gap: 24px;
        }

        .dd-step-icon {
            flex-shrink: 0;
            width: 40px;
            height: 40px;
            background: var(--dd-bg-primary);
            border: 2px solid var(--dd-border);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.25rem;
            box-shadow: 0 4px 12px rgba(0,0,0,0.03);
            transition: all 0.3s ease;
        }

        .dd-step:hover .dd-step-icon {
            border-color: var(--dd-accent);
            transform: scale(1.1);
        }

        .dd-step-content {
            flex: 1;
        }

        .dd-step-label {
            font-size: 0.75rem;
            font-weight: 700;
            color: var(--dd-accent);
            text-transform: uppercase;
            letter-spacing: 0.1em;
            margin-bottom: 4px;
        }

        .dd-step-title {
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--dd-text-primary);
            margin: 0 0 16px 0;
        }

        .dd-text {
            line-height: 1.7;
            font-size: 1rem;
        }

        .dd-text p { margin-bottom: 16px; }
        .dd-text p:last-child { margin-bottom: 0; }

        .dd-list {
            list-style: none;
            padding: 0;
            margin: 0;
            display: grid;
            gap: 12px;
        }

        .dd-list-item {
            background: var(--dd-bg-secondary);
            padding: 16px 20px;
            border-radius: 12px;
            border-left: 4px solid var(--dd-border);
            transition: all 0.2s ease;
        }

        .dd-list-item:hover {
            background: var(--dd-bg-tertiary);
            border-left-color: var(--dd-accent);
            transform: translateX(4px);
        }

        .dd-list-item strong {
            color: var(--dd-text-primary);
            display: block;
            margin-bottom: 4px;
        }

        .dd-path-item {
            background: var(--dd-accent-soft);
            border-left-color: var(--dd-accent);
        }

        .dd-footer {
            padding: 24px 32px;
            background: var(--dd-bg-secondary);
            border-top: 1px solid var(--dd-border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.8rem;
            color: var(--dd-text-dim);
        }

        .dd-tag {
            padding: 2px 8px;
            background: var(--dd-bg-tertiary);
            border-radius: 4px;
            font-weight: 600;
        }

        .dd-text code,
        .dd-list-item code {
            background: var(--dd-code-bg);
            color: var(--dd-text-primary);
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'SF Mono', 'Consolas', 'Monaco', monospace;
            font-size: 0.85em;
        }

        .dd-list-item em {
            font-style: italic;
            color: var(--dd-text-dim);
        }
"""

CONTENT_TEMPLATE = """
        <div class="deep-dive">
            <div class="dd-header">
                <div class="dd-header-badge">{{badge}}</div>
                <h1 class="dd-title">{{title}}</h1>
                <div class="dd-meta">
                    <span>👤 {user_name}</span>
                    <span>📅 {current_date_time_str}</span>
                    <span>📊 {word_count} {{word_count_label}}</span>
                </div>
            </div>
            <div class="dd-body">
                <!-- Step 1: Context -->
                <div class="dd-step">
                    <div class="dd-step-icon">🔍</div>
                    <div class="dd-step-content">
                        <div class="dd-step-label">{{phase_01}}</div>
                        <h2 class="dd-step-title">{{context_label}}</h2>
                        <div class="dd-text">{context_html}</div>
                    </div>
                </div>

                <!-- Step 2: Logic -->
                <div class="dd-step">
                    <div class="dd-step-icon">🧠</div>
                    <div class="dd-step-content">
                        <div class="dd-step-label">{{phase_02}}</div>
                        <h2 class="dd-step-title">{{logic_label}}</h2>
                        <div class="dd-text">{logic_html}</div>
                    </div>
                </div>

                <!-- Step 3: Insight -->
                <div class="dd-step">
                    <div class="dd-step-icon">💎</div>
                    <div class="dd-step-content">
                        <div class="dd-step-label">{{phase_03}}</div>
                        <h2 class="dd-step-title">{{insight_label}}</h2>
                        <div class="dd-text">{insight_html}</div>
                    </div>
                </div>

                <!-- Step 4: Path -->
                <div class="dd-step">
                    <div class="dd-step-icon">🚀</div>
                    <div class="dd-step-content">
                        <div class="dd-step-label">{{phase_04}}</div>
                        <h2 class="dd-step-title">{{path_label}}</h2>
                        <div class="dd-text">{path_html}</div>
                    </div>
                </div>
            </div>
            <div class="dd-footer">
                <span>{{footer_engine}}</span>
                <span><span class="dd-tag">{{footer_tag}}</span></span>
            </div>
        </div>
"""


class Action:
    class Valves(BaseModel):
        SHOW_STATUS: bool = Field(
            default=True,
            description="Whether to show operation status updates.",
        )
        SHOW_DEBUG_LOG: bool = Field(
            default=False,
            description="Whether to print debug logs in the browser console.",
        )
        MODEL_ID: str = Field(
            default="",
            description="LLM Model ID for analysis. Empty = use current model.",
        )
        MIN_TEXT_LENGTH: int = Field(
            default=200,
            description="Minimum text length for deep dive (chars).",
        )
        CLEAR_PREVIOUS_HTML: bool = Field(
            default=True,
            description="Whether to clear previous plugin results.",
        )
        MESSAGE_COUNT: int = Field(
            default=1,
            description="Number of recent messages to analyze.",
        )

    def __init__(self):
        self.valves = self.Valves()

    def _resolve_language(self, language: str) -> str:
        """Resolves language code to supported translation keys."""
        if language in TRANSLATIONS:
            return language
        return LANGUAGE_FALLBACKS.get(language, "en-US")

    def _get_translation(self, language: str) -> Dict[str, str]:
        """Gets the translation dictionary for the given language."""
        lang_key = self._resolve_language(language)
        return TRANSLATIONS.get(lang_key, TRANSLATIONS["en-US"])

    def _get_prompt(self, language: str, prompt_type: str) -> str:
        """Gets the prompt for the given language and type."""
        lang_key = self._resolve_language(language)
        if lang_key not in PROMPTS:
            lang_key = "en-US"
        return PROMPTS[lang_key][prompt_type]

    async def _get_user_context(
        self,
        __user__: Optional[Dict[str, Any]],
        __event_call__: Optional[Callable[[Any], Awaitable[None]]] = None,
        __request__: Optional[Request] = None,
    ) -> Dict[str, str]:
        """Safely extracts user context information."""
        if isinstance(__user__, (list, tuple)):
            user_data = __user__[0] if __user__ else {}
        elif isinstance(__user__, dict):
            user_data = __user__
        else:
            user_data = {}

        user_id = user_data.get("id", "unknown_user")
        user_name = user_data.get("name", "User")
        # Default from profile
        user_language = user_data.get("language", "en-US")

        # Level 1 Fallback: Accept-Language from __request__ headers
        if (
            __request__
            and hasattr(__request__, "headers")
            and "accept-language" in __request__.headers
        ):
            raw_lang = __request__.headers.get("accept-language", "")
            if raw_lang:
                user_language = raw_lang.split(",")[0].split(";")[0]

        # Priority: Document Lang > LocalStorage (Frontend) > Browser > Request Header > Profile
        if __event_call__:
            try:
                js_code = """
                    try {
                        return (
                            document.documentElement.lang ||
                            localStorage.getItem('locale') || 
                            localStorage.getItem('language') || 
                            navigator.language || 
                            'en-US'
                        );
                    } catch (e) {
                        return 'en-US';
                    }
                """
                # Use asyncio.wait_for to prevent hanging if frontend fails to callback
                frontend_lang = await asyncio.wait_for(
                    __event_call__({"type": "execute", "data": {"code": js_code}}),
                    timeout=2.0,
                )
                if frontend_lang and isinstance(frontend_lang, str):
                    user_language = frontend_lang
            except Exception as e:
                logger.warning(f"Failed to retrieve frontend language: {e}")

        return {
            "user_id": user_id,
            "user_name": user_name,
            "user_language": user_language,
        }

    def _get_chat_context(
        self, body: dict, __metadata__: Optional[dict] = None
    ) -> Dict[str, str]:
        """
        Unified extraction of chat context information (chat_id, message_id).
        Prioritizes extraction from body, then metadata.
        """
        chat_id = ""
        message_id = ""

        # 1. Try to get from body
        if isinstance(body, dict):
            chat_id = body.get("chat_id", "")
            message_id = body.get("id", "")  # message_id is usually 'id' in body

            # Check body.metadata as fallback
            if not chat_id or not message_id:
                body_metadata = body.get("metadata", {})
                if isinstance(body_metadata, dict):
                    if not chat_id:
                        chat_id = body_metadata.get("chat_id", "")
                    if not message_id:
                        message_id = body_metadata.get("message_id", "")

        # 2. Try to get from __metadata__ (as supplement)
        if __metadata__ and isinstance(__metadata__, dict):
            if not chat_id:
                chat_id = __metadata__.get("chat_id", "")
            if not message_id:
                message_id = __metadata__.get("message_id", "")

        return {
            "chat_id": str(chat_id).strip(),
            "message_id": str(message_id).strip(),
        }

    def _extract_json(self, text: str) -> Optional[dict]:
        """
        Robustly extracts JSON from a string that may contain extra text or Markdown blocks.
        """
        if not text:
            return None

        # 1. Try to find content within triple backticks (JSON code blocks)
        # Supports ```json ... ``` or just ``` ... ```
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if json_match:
            try:
                content = json_match.group(1).strip()
                return json.loads(content)
            except json.JSONDecodeError:
                # If the content inside backticks is not valid JSON, 
                # we fall back to searching the whole string for the outer {}
                text = json_match.group(1).strip()

        # 2. Find the first '{' and last '}' (Greedy extraction)
        start_index = text.find("{")
        end_index = text.rfind("}")

        if start_index != -1 and end_index != -1:
            json_str = text[start_index : end_index + 1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                # Last resort: try to clean up some common issues like trailing commas
                try:
                    # Very simple cleanup for trailing commas in arrays/objects
                    # Note: This is risky, but better than total failure
                    cleaned_str = re.sub(r",\s*([\]}])", r"\1", json_str)
                    return json.loads(cleaned_str)
                except Exception:
                    pass

        return None

    def _process_llm_output(self, llm_output: str, i18n: dict) -> Dict[str, str]:
        """
        Parse JSON LLM output and convert to styled HTML.
        """
        try:
            # 1. Extract JSON with high fault tolerance
            data = self._extract_json(llm_output)
            if not data:
                raise ValueError("Failed to extract valid JSON from LLM response.")
            
            # 2. Extract sections
            context_raw = data.get("context", "")
            logic_raw = data.get("logic", [])
            insight_raw = data.get("insight", [])
            path_raw = data.get("path", [])

            # 3. Render sections to HTML
            context_html = markdown.markdown(context_raw, extensions=["nl2br"]) if context_raw else ""
            logic_html = self._render_json_list(logic_raw, "logic", i18n)
            insight_html = self._render_json_list(insight_raw, "insight", i18n)
            path_html = self._render_json_list(path_raw, "path", i18n)

            return {
                "context_html": context_html,
                "logic_html": logic_html,
                "insight_html": insight_html,
                "path_html": path_html,
            }
        except Exception as e:
            logger.error(f"Failed to parse JSON output: {e}")
            # Fallback: treat as raw text context
            return {
                "context_html": markdown.markdown(llm_output, extensions=["nl2br"]),
                "logic_html": "",
                "insight_html": "",
                "path_html": "",
            }

    def _render_json_list(self, items: List[Dict[str, str]], section_type: str, i18n: dict) -> str:
        """Renders list items from JSON data into styled HTML cards."""
        if not items or not isinstance(items, list):
            fallback_key = f"no_{section_type}"
            return f'<p class="dd-no-content">{i18n.get(fallback_key, "No items found.")}</p>'

        html_items = []
        for item in items:
            title = self._convert_inline_markdown(str(item.get("title", "")))
            content = self._convert_inline_markdown(str(item.get("content", "")))
            
            path_class = "dd-path-item" if section_type == "path" else ""
            if title:
                item_html = f'<div class="dd-list-item {path_class}"><strong>{title}</strong>{content}</div>'
            else:
                item_html = f'<div class="dd-list-item {path_class}">{content}</div>'
            html_items.append(item_html)

        return f'<div class="dd-list">{" ".join(html_items)}</div>'



    def _convert_inline_markdown(self, text: str) -> str:
        """Convert inline markdown (bold, italic, code) to HTML."""
        # Convert inline code: `code` -> <code>code</code>
        text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
        # Convert bold: **text** -> <strong>text</strong>
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        # Convert italic: *text* -> <em>text</em> (but not inside **)
        text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
        return text

    async def _emit_status(
        self,
        emitter: Optional[Callable[[Any], Awaitable[None]]],
        description: str,
        done: bool = False,
    ):
        """Emits a status update event."""
        if self.valves.SHOW_STATUS and emitter:
            await emitter(
                {"type": "status", "data": {"description": description, "done": done}}
            )

    async def _emit_notification(
        self,
        emitter: Optional[Callable[[Any], Awaitable[None]]],
        content: str,
        ntype: str = "info",
    ):
        """Emits a notification event."""
        if emitter:
            await emitter(
                {"type": "notification", "data": {"type": ntype, "content": content}}
            )

    async def _emit_debug_log(self, emitter, title: str, data: dict):
        """Print structured debug logs in the browser console"""
        if not self.valves.SHOW_DEBUG_LOG or not emitter:
            return

        try:
            import json

            js_code = f"""
                (async function() {{
                    console.group("🛠️ {title}");
                    console.log({json.dumps(data, ensure_ascii=False)});
                    console.groupEnd();
                }})();
            """

            await emitter({"type": "execute", "data": {"code": js_code}})
        except Exception as e:
            print(f"Error emitting debug log: {e}")

    def _remove_existing_html(self, content: str) -> str:
        """Removes existing plugin-generated HTML."""
        pattern = r"```html\s*<!-- OPENWEBUI_PLUGIN_OUTPUT -->[\s\S]*?```"
        return re.sub(pattern, "", content).strip()

    def _extract_text_content(self, content) -> str:
        """Extract text from message content."""
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                elif isinstance(item, str):
                    text_parts.append(item)
            return "\n".join(text_parts)
        return str(content) if content else ""

    def _merge_html(
        self,
        existing_html: str,
        new_content: str,
        new_styles: str = "",
        user_language: str = "en-US",
    ) -> str:
        """Merges new content into HTML container."""
        if "<!-- OPENWEBUI_PLUGIN_OUTPUT -->" in existing_html:
            base_html = re.sub(r"^```html\s*", "", existing_html)
            base_html = re.sub(r"\s*```$", "", base_html)
        else:
            base_html = HTML_WRAPPER_TEMPLATE.replace("{user_language}", user_language)

        wrapped = f'<div class="plugin-item">\n{new_content}\n</div>'

        if new_styles:
            base_html = base_html.replace(
                "/* STYLES_INSERTION_POINT */",
                f"{new_styles}\n/* STYLES_INSERTION_POINT */",
            )

        base_html = base_html.replace(
            "<!-- CONTENT_INSERTION_POINT -->",
            f"{wrapped}\n<!-- CONTENT_INSERTION_POINT -->",
        )

        return base_html.strip()

    def _build_content_html(self, context: dict, i18n: dict) -> str:
        """Build content HTML."""
        html = CONTENT_TEMPLATE
        # Fill i18n placeholders
        for key, value in i18n.items():
            html = html.replace(f"{{{{{key}}}}}", str(value))

        # Fill data placeholders
        for key, value in context.items():
            if value == "":
                fallback_key = f"no_{key.replace('_html', '')}"
                value = f'<p class="dd-no-content">{i18n.get(fallback_key, "")}</p>'
            html = html.replace(f"{{{key}}}", str(value))
        return html

    async def action(
        self,
        body: dict,
        __user__: Optional[Dict[str, Any]] = None,
        __event_emitter__: Optional[Callable[[Any], Awaitable[None]]] = None,
        __event_call__: Optional[Callable[[Any], Awaitable[None]]] = None,
        __request__: Optional[Request] = None,
    ) -> Optional[dict]:
        logger.info("Action: Deep Dive v1.1.0 started")

        user_ctx = await self._get_user_context(
            __user__, __event_call__, __request__
        )
        user_id = user_ctx["user_id"]
        user_name = user_ctx["user_name"]
        user_language = user_ctx["user_language"]
        i18n = self._get_translation(user_language)

        now = datetime.now()
        current_date_time_str = now.strftime("%b %d, %Y %H:%M")

        original_content = ""
        try:
            messages = body.get("messages", [])
            if not messages:
                raise ValueError("No messages found.")

            message_count = min(self.valves.MESSAGE_COUNT, len(messages))
            recent_messages = messages[-message_count:]

            aggregated_parts = []
            for msg in recent_messages:
                text = self._extract_text_content(msg.get("content"))
                if text:
                    aggregated_parts.append(text)

            if not aggregated_parts:
                raise ValueError("No text content found.")

            original_content = "\n\n---\n\n".join(aggregated_parts)
            word_count = len(original_content.split())

            if len(original_content) < self.valves.MIN_TEXT_LENGTH:
                msg = i18n["error_brief"].format(
                    length=len(original_content),
                    min_length=self.valves.MIN_TEXT_LENGTH,
                )
                await self._emit_notification(__event_emitter__, msg, "warning")
                return {"messages": [{"role": "assistant", "content": f"⚠️ {msg}"}]}

            await self._emit_notification(
                __event_emitter__, i18n["notification_initiating"], "info"
            )
            await self._emit_status(
                __event_emitter__, i18n["status_analyzing"], False
            )

            prompt = self._get_prompt(user_language, "user").format(
                user_name=user_name,
                current_date_time_str=current_date_time_str,
                user_language=user_language,
                long_text_content=original_content,
            )

            model = self.valves.MODEL_ID or body.get("model")
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": self._get_prompt(user_language, "system"),
                    },
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
            }

            user_obj = await _call_db(Users.get_user_by_id, user_id)
            if not user_obj:
                raise ValueError(f"User not found: {user_id}")

            response = await generate_chat_completion(__request__, payload, user_obj)
            llm_output = response["choices"][0]["message"]["content"]

            # 5. Process Output using JSON parser
            processed = self._process_llm_output(llm_output, i18n)

            context = {
                "user_name": user_name,
                "current_date_time_str": current_date_time_str,
                "word_count": word_count,
                **processed,
            }

            content_html = self._build_content_html(context, i18n)

            # 6. Handle existing HTML and Merge
            existing = ""
            match = re.search(
                r"```html\s*(<!-- OPENWEBUI_PLUGIN_OUTPUT -->[\s\S]*?)```",
                original_content,
            )
            if match:
                existing = match.group(1)

            if self.valves.CLEAR_PREVIOUS_HTML or not existing:
                original_content = self._remove_existing_html(original_content)
                final_html = self._merge_html(
                    "", content_html, CSS_TEMPLATE, user_language
                )
            else:
                original_content = self._remove_existing_html(original_content)
                final_html = self._merge_html(
                    existing, content_html, CSS_TEMPLATE, user_language
                )

            body["messages"][-1][
                "content"
            ] = f"{original_content}\n\n```html\n{final_html}\n```"

            await self._emit_status(__event_emitter__, i18n["status_complete"], True)
            await self._emit_notification(
                __event_emitter__,
                i18n["notification_complete"].format(user_name=user_name),
                "success",
            )

        except Exception as e:
            logger.error(f"Deep Dive Error: {e}", exc_info=True)
            body["messages"][-1][
                "content"
            ] = f"{original_content}\n\n❌ **Error:** {str(e)}"
            await self._emit_status(__event_emitter__, "Deep Dive failed.", True)
            await self._emit_notification(
                __event_emitter__, f"Error: {str(e)}", "error"
            )

        return body
