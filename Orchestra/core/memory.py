"""
Orchestra of Experts - Memory Palace

Long-term memory for the Orchestra, organised using the classic
Memory Palace structure (inspired by MemPalace by Milla Jovovich & Ben Sigman):

  Palace
    └── Wing     (project / person / major context)
          └── Room    (topic)
                └── Drawer  (verbatim memory entry)

Design goals:
- Local-first, no cloud required
- Simple enough to work offline with zero extra deps at first
- Structured so we can later swap the backend for full MemPalace
  (or ChromaDB) without rewriting the Conductor

Storage layout (default):
  Orchestra/core/palace/
    wings/
      <wing_name>/
        rooms/
          <room_name>/
            drawers/
              <timestamp>_<id>.json
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


class MemoryPalace:
    def __init__(self, palace_root: str | Path | None = None):
        """
        palace_root defaults to Orchestra/core/palace/
        """
        if palace_root is None:
            palace_root = Path(__file__).resolve().parent / "palace"

        self.root = Path(palace_root)
        self.wings_dir = self.root / "wings"
        self.wings_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------
    def _wing_path(self, wing: str) -> Path:
        return self.wings_dir / self._safe_name(wing)

    def _room_path(self, wing: str, room: str) -> Path:
        return self._wing_path(wing) / "rooms" / self._safe_name(room)

    def _drawers_path(self, wing: str, room: str) -> Path:
        return self._room_path(wing, room) / "drawers"

    @staticmethod
    def _safe_name(name: str) -> str:
        """Make a filesystem-safe name."""
        return "".join(c if c.isalnum() or c in "-_" else "_" for c in name.strip()).strip("_") or "unnamed"

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------
    def remember(
        self,
        content: str,
        wing: str = "default",
        room: str = "general",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict:
        """
        Store a verbatim memory (a Drawer).

        Returns the stored drawer as a dict.
        """
        drawers_dir = self._drawers_path(wing, room)
        drawers_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now(timezone.utc)
        drawer_id = str(uuid.uuid4())[:8]
        filename = f"{now.strftime('%Y%m%dT%H%M%S')}_{drawer_id}.json"

        drawer = {
            "id": drawer_id,
            "wing": wing,
            "room": room,
            "content": content,
            "tags": tags or [],
            "metadata": metadata or {},
            "created_at": now.isoformat(),
        }

        path = drawers_dir / filename
        path.write_text(json.dumps(drawer, indent=2, ensure_ascii=False), encoding="utf-8")

        return drawer

    # ------------------------------------------------------------------
    # Read / Search
    # ------------------------------------------------------------------
    def list_wings(self) -> list[str]:
        if not self.wings_dir.exists():
            return []
        return sorted(
            p.name for p in self.wings_dir.iterdir() if p.is_dir()
        )

    def list_rooms(self, wing: str) -> list[str]:
        rooms_dir = self._wing_path(wing) / "rooms"
        if not rooms_dir.exists():
            return []
        return sorted(
            p.name for p in rooms_dir.iterdir() if p.is_dir()
        )

    def _iter_drawers(
        self,
        wing: str | None = None,
        room: str | None = None,
    ):
        """Yield (path, drawer_dict) for matching drawers."""
        wings = [wing] if wing else self.list_wings()

        for w in wings:
            rooms = [room] if room else self.list_rooms(w)
            for r in rooms:
                drawers_dir = self._drawers_path(w, r)
                if not drawers_dir.exists():
                    continue
                for path in sorted(drawers_dir.glob("*.json"), reverse=True):
                    try:
                        data = json.loads(path.read_text(encoding="utf-8"))
                        yield path, data
                    except Exception:
                        continue

    def search(
        self,
        query: str,
        wing: str | None = None,
        room: str | None = None,
        limit: int = 5,
    ) -> list[dict]:
        """
        Simple keyword search over drawer content + tags.

        This is intentionally lightweight. Later we can replace the
        internals with MemPalace / ChromaDB semantic search while
        keeping the same public API.
        """
        query_lower = query.lower().strip()
        if not query_lower:
            return []

        results = []
        for _, drawer in self._iter_drawers(wing=wing, room=room):
            content = drawer.get("content", "").lower()
            tags = " ".join(drawer.get("tags", [])).lower()
            haystack = f"{content} {tags}"

            if query_lower in haystack:
                results.append(drawer)
                if len(results) >= limit:
                    break

        return results

    def recent(
        self,
        wing: str | None = None,
        room: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Return the most recent drawers."""
        results = []
        for _, drawer in self._iter_drawers(wing=wing, room=room):
            results.append(drawer)
            if len(results) >= limit:
                break
        return results

    # ------------------------------------------------------------------
    # Convenience for the Conductor
    # ------------------------------------------------------------------
    def recall_for_prompt(
        self,
        query: str,
        wing: str | None = None,
        limit: int = 3,
    ) -> str:
        """
        Build a short context block the Conductor / experts can inject
        into a prompt.
        """
        hits = self.search(query, wing=wing, limit=limit)
        if not hits:
            return ""

        lines = ["[Memory Palace – relevant past notes]"]
        for h in hits:
            wing_name = h.get("wing", "?")
            room_name = h.get("room", "?")
            content = h.get("content", "").strip()
            # Keep each memory reasonably short in the prompt
            if len(content) > 400:
                content = content[:400] + "…"
            lines.append(f"- ({wing_name}/{room_name}) {content}")

        return "\n".join(lines)

    def status(self) -> dict:
        """Quick overview of the palace."""
        wings = self.list_wings()
        total_drawers = 0
        rooms_count = 0

        for w in wings:
            rooms = self.list_rooms(w)
            rooms_count += len(rooms)
            for r in rooms:
                drawers_dir = self._drawers_path(w, r)
                if drawers_dir.exists():
                    total_drawers += len(list(drawers_dir.glob("*.json")))

        return {
            "palace_root": str(self.root),
            "wings": len(wings),
            "rooms": rooms_count,
            "drawers": total_drawers,
            "wing_names": wings,
        }


if __name__ == "__main__":
    # Quick manual test
    palace = MemoryPalace()
    print("Palace status:", palace.status())

    palace.remember(
        "User prefers energy weapons with infinite ammo in Armored Core 6.",
        wing="personal",
        room="gaming",
        tags=["ac6", "preference"],
    )
    palace.remember(
        "Working on Orchestra of Experts – sequential MoE with hot-swapped GGUF experts.",
        wing="orchestra",
        room="architecture",
        tags=["moe", "design"],
    )

    print("\nSearch 'ac6':")
    for d in palace.search("ac6"):
        print(" ", d["content"][:80])

    print("\nRecall block:")
    print(palace.recall_for_prompt("gaming preferences"))
