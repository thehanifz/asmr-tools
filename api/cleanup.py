import os
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/cleanup", tags=["cleanup"])

class CleanupRequest(BaseModel):
    workspace: str

@router.post("/")
def auto_cleanup(req: CleanupRequest):
    """Hapus semua file _tmp_ di dalam folder workspace."""
    if not req.workspace or not os.path.isdir(req.workspace):
        return {"status": "error", "message": "Workspace tidak valid"}

    deleted_files = []
    try:
        for root, dirs, files in os.walk(req.workspace):
            for file in files:
                if file.startswith("_tmp_"):
                    filepath = os.path.join(root, file)
                    try:
                        os.remove(filepath)
                        deleted_files.append(file)
                    except Exception as e:
                        print(f"Gagal hapus {filepath}: {e}")

        return {
            "status": "success",
            "message": f"Berhasil menghapus {len(deleted_files)} file sementara (_tmp_).",
            "deleted_count": len(deleted_files)
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
