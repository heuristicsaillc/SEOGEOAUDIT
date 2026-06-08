"""FastAPI application: the JSON API + serving the built React frontend.

Mounts the audit endpoints under /api and serves frontend/dist (when present)
as the single deployable unit described in the technical design.
"""

from __future__ import annotations  # Forward references for typing

from pathlib import Path  # Locate the built frontend directory
from urllib.parse import urlparse  # Extract host for PDF filenames

from fastapi import APIRouter, FastAPI, HTTPException  # ASGI app + routing
from fastapi.middleware.cors import CORSMiddleware  # Allow the dev frontend to call the API
from fastapi.responses import JSONResponse, Response  # JSON errors + raw PDF bytes
from fastapi.staticfiles import StaticFiles  # Serve the built frontend assets
from starlette.types import Scope  # ASGI scope typing

from app.models import AuditRequest, AuditResponse, ReportPdfRequest  # Request/response models
from app.orchestrator import AuditOrchestrator  # Runs the audit pipeline
from app.pdf_export import build_report_pdf  # PDF generator

# Path to the built React app (frontend/dist) relative to this file
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

# One orchestrator instance is reused across requests (it is stateless per run)
_orchestrator = AuditOrchestrator()


class SPAStaticFiles(StaticFiles):
    """Static file server for the React build that never handles /api/* paths.

    Without this guard, unknown POST /api/* requests fall through to StaticFiles
    and return 405 Method Not Allowed instead of a clear API error.
    """

    async def __call__(self, scope: Scope, receive, send) -> None:
        """Serve static assets, but reject /api/* so API routes handle those paths."""
        if scope["type"] == "http" and scope["path"].startswith("/api"):
            response = JSONResponse(  # Clear JSON error instead of StaticFiles 405
                {"detail": "API route not found. Restart the backend server and try again."},
                status_code=404,
            )
            await response(scope, receive, send)
            return
        await super().__call__(scope, receive, send)


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application."""
    app = FastAPI(  # Create the app with descriptive metadata
        title="SEO & GEO Auditor",  # API title
        description="Audits a website for SEO and GEO, scoring each and returning two reports.",
        version="1.0.0",  # API version
    )

    # Allow cross-origin calls so the Vite dev server (port 5173) can reach the API
    app.add_middleware(
        CORSMiddleware,  # Standard CORS middleware
        allow_origins=["*"],  # Permissive for local development
        allow_methods=["*"],  # Allow all HTTP methods
        allow_headers=["*"],  # Allow all headers
    )

    api = APIRouter(prefix="/api")  # All JSON endpoints live under /api

    @api.get("/health")
    async def health() -> dict:
        """Liveness probe used by the frontend and deployment checks."""
        return {"status": "ok"}  # Simple readiness response

    @api.post("/audit", response_model=AuditResponse)
    async def audit(request: AuditRequest) -> AuditResponse:
        """Run a full SEO + GEO audit for the requested URL and return both reports."""
        if not request.url or not request.url.strip():  # Reject empty input early
            raise HTTPException(status_code=400, detail="A non-empty 'url' is required.")  # 400
        try:  # The orchestrator is defensive, but surface unexpected failures clearly
            return await _orchestrator.run(request.url)  # Execute the audit pipeline
        except Exception as exc:  # Catastrophic failure (should be rare)
            raise HTTPException(status_code=500, detail=f"Audit failed: {exc}") from exc  # 500

    @api.post("/report/pdf")
    async def report_pdf(request: ReportPdfRequest) -> Response:
        """Generate a downloadable PDF for one SEO or GEO report."""
        try:  # PDF layout can fail on unexpected content
            pdf_bytes = build_report_pdf(  # Render the report
                request.report,
                final_url=request.final_url,
                duration_seconds=request.duration_seconds,
                connected=request.connected,
            )
        except Exception as exc:  # Surface a clear error to the UI
            raise HTTPException(status_code=500, detail=f"PDF export failed: {exc}") from exc

        host = urlparse(request.final_url).netloc.replace("www.", "") or "site"  # Filename host
        filename = f"{request.report.kind}-audit-{host}.pdf"
        return Response(  # Stream the PDF as a file download
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    app.include_router(api)  # Register API routes before the static mount

    # Serve the built frontend if it exists (production single-unit deployment)
    if FRONTEND_DIST.exists():  # Only mount when the React app has been built
        # html=True serves index.html for unknown paths (SPA routing)
        app.mount("/", SPAStaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
    else:  # During development the frontend runs separately on Vite

        @app.get("/", response_model=None)  # Disable response-model inference for this helper
        async def root() -> dict:
            """Root response when no built frontend is present."""
            return {  # Point developers at the API + dev instructions
                "service": "SEO & GEO Auditor API",
                "docs": "/docs",
                "hint": "Build the frontend (npm run build) or run the Vite dev server.",
            }

    return app  # The configured application


# The ASGI application object uvicorn imports: `uvicorn app.main:app`
app = create_app()  # Construct the app at import time
