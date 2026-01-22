"""
Widget serving endpoints for external integration.

This module provides endpoints to serve the CiVers widget as a centrally-hosted,
self-contained solution that can be integrated into external sites with a single
script tag.
"""

from fastapi import APIRouter, Response
from fastapi.responses import FileResponse, HTMLResponse
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/widget", tags=["Widget"])

# Get the static widget directory
WIDGET_DIR = Path(__file__).parent.parent.parent / "static" / "widget"


@router.get("/civers-widget.js")
async def serve_widget_js():
    """Serve the self-contained widget JavaScript file."""
    widget_path = WIDGET_DIR / "civers-widget.js"
    if not widget_path.exists():
        logger.error(f"Widget JavaScript not found at {widget_path}")
        return Response(content="// Widget not found", media_type="application/javascript", status_code=404)
    
    return FileResponse(
        widget_path,
        media_type="application/javascript",
        headers={
            "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
            "Access-Control-Allow-Origin": "*"
        }
    )


@router.get("/civers-widget.css")
async def serve_widget_css():
    """Serve the widget CSS file."""
    css_path = WIDGET_DIR / "civers-widget.css"
    if not css_path.exists():
        logger.error(f"Widget CSS not found at {css_path}")
        return Response(content="/* Widget CSS not found */", media_type="text/css", status_code=404)
    
    return FileResponse(
        css_path,
        media_type="text/css",
        headers={
            "Cache-Control": "public, max-age=3600",
            "Access-Control-Allow-Origin": "*"
        }
    )


@router.get("/demo.html")
async def widget_demo():
    """
    Serve a demo page showing how to integrate the widget.
    
    This page provides:
    - Live widget demonstration
    - Integration code examples
    - Configuration options
    """
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>CiVers Widget Integration Demo</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                max-width: 1200px;
                margin: 0 auto;
                padding: 40px 20px;
                background: #f5f5f5;
            }
            .hero {
                background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%);
                color: white;
                padding: 60px 40px;
                border-radius: 20px;
                margin-bottom: 40px;
                text-align: center;
            }
            .hero h1 {
                margin: 0 0 20px 0;
                font-size: 3em;
            }
            .hero p {
                font-size: 1.3em;
                opacity: 0.9;
            }
            .section {
                background: white;
                padding: 40px;
                border-radius: 16px;
                margin-bottom: 30px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }
            h2 {
                margin-top: 0;
                color: #1e1b4b;
            }
            pre {
                background: #f8f9fa;
                padding: 20px;
                border-radius: 8px;
                overflow-x: auto;
                border-left: 4px solid #312e81;
            }
            code {
                font-family: 'Monaco', 'Menlo', monospace;
                font-size: 14px;
            }
            .alert {
                background: #e0e7ff;
                border-left: 4px solid #4f46e5;
                padding: 15px 20px;
                border-radius: 8px;
                margin: 20px 0;
            }
            .badge {
                display: inline-block;
                background: #10b981;
                color: white;
                padding: 4px 12px;
                border-radius: 12px;
                font-size: 0.875em;
                font-weight: 600;
                margin-left: 10px;
            }
        </style>
    </head>
    <body>
        <div class="hero">
            <h1>🏛️ CiVers Widget</h1>
            <p>Archaeological Web Archiving Made Simple</p>
            <span class="badge">v1.0</span>
        </div>

        <div class="section">
            <h2>✨ Quick Start</h2>
            <p>Add CiVers archiving to your site with just one line of code:</p>
            
            <pre><code>&lt;!-- Add this to your HTML --&gt;
&lt;script src="http://localhost:8000/widget/civers-widget.js"
        data-api-url="http://localhost:8000"
        async&gt;&lt;/script&gt;</code></pre>

            <div class="alert">
                <strong>✅ That's it!</strong> The widget will automatically appear and work on your site.
                It even detects SPA navigation in React, Vue, Angular, and AngularJS applications.
            </div>
        </div>

        <div class="section">
            <h2>⚙️ Configuration Options</h2>
            <pre><code>&lt;script src="http://localhost:8000/widget/civers-widget.js"
        data-widget-target="#custom-container"
        data-api-url="http://localhost:8000"
        data-position="bottom-right"
        data-theme="light"
        async&gt;&lt;/script&gt;

&lt;!-- Optional: Specify a custom container --&gt;
&lt;div id="custom-container"&gt;&lt;/div&gt;</code></pre>

            <table style="width: 100%; margin-top: 20px; border-collapse: collapse;">
                <tr style="border-bottom: 2px solid #e5e7eb;">
                    <th style="text-align: left; padding: 10px;">Option</th>
                    <th style="text-align: left; padding: 10px;">Default</th>
                    <th style="text-align: left; padding: 10px;">Description</th>
                </tr>
                <tr style="border-bottom: 1px solid #e5e7eb;">
                    <td style="padding: 10px;"><code>data-api-url</code></td>
                    <td style="padding: 10px;">(required)</td>
                    <td style="padding: 10px;">CiVers API base URL</td>
                </tr>
                <tr style="border-bottom: 1px solid #e5e7eb;">
                    <td style="padding: 10px;"><code>data-widget-target</code></td>
                    <td style="padding: 10px;">#civers-widget-root</td>
                    <td style="padding: 10px;">Container selector</td>
                </tr>
                <tr style="border-bottom: 1px solid #e5e7eb;">
                    <td style="padding: 10px;"><code>data-position</code></td>
                    <td style="padding: 10px;">bottom-right</td>
                    <td style="padding: 10px;">bottom-right, bottom-left, etc.</td>
                </tr>
                <tr>
                    <td style="padding: 10px;"><code>data-theme</code></td>
                    <td style="padding: 10px;">light</td>
                    <td style="padding: 10px;">light or dark</td>
                </tr>
            </table>
        </div>

        <div class="section">
            <h2>🚀 Features</h2>
            <ul style="line-height: 1.8;">
                <li>✅ <strong>Zero Configuration</strong> - Works out of the box</li>
                <li>✅ <strong>SPA Compatible</strong> - Auto-detects navigation in React, Vue, Angular</li>
                <li>✅ <strong>Style Isolated</strong> - Uses Shadow DOM to prevent CSS conflicts</li>
                <li>✅ <strong>Auto Updates</strong> - Always serves the latest version</li>
                <li>✅ <strong>Responsive</strong> - Works on desktop and mobile</li>
                <li>✅ <strong>Secure</strong> - CORS-enabled for cross-origin integration</li>
            </ul>
        </div>

        <div class="section">
            <h2>📖 Live Demo</h2>
            <p><strong>This page includes the widget!</strong> Look for the floating icon in the bottom-right corner.</p>
            <div class="alert">
                Try clicking the 🏛️ icon to see the widget in action.
            </div>
        </div>

        <!-- Include the actual widget -->
        <script src="/widget/civers-widget.js"
                data-api-url="http://localhost:8000"
                async></script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)
