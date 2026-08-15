solution_821.python

```python
import os
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

"""
Bounty: Engine Support: Roblox Studio path for Goal to Game Skill
File: solution_821.python

Deliverable: A Python class defining the 'Roblox' engine logic.
The Goal to Game pipeline reads this object to understand:
1. Geometry Constraints (20k Triangles, Watertight)
2. Hierarchy (Main Model vs Workspace)
3. Scale (100 units = 1 meter)
"""

@dataclass
class RobloxEngine:
    # --- Core Identity ---
    name: str = "Roblox"
    engine_type: str = "Rigged"
    
    # --- Path Configuration ---
    # Matches the 'engines/unity.md' folder structure pattern
    root_path: str = "engines/roblox"
    
    # --- The "Import Boundary" Constraints ---
    # Roblox is stricter on import geometry than Unity/ThreeJS.
    geometry_caps: Dict[str, Any] = field(
        default_factory=lambda: {
            "max_triangulation": 20_000,
            "watertight_required": True,
            "units_per_meter": 100.0,
            "axis_orientation": "Y-Up"
        }
    )
    
    # --- Hierarchy Logic ---
    hierarchy: Dict[str, Any] = field(
        default_factory=lambda: {
            "workspace_root": "Workspace",
            "primary_container": "Main"
        }
    )
    
    # --- Asset Bucket ---
    asset_folder: str = "Content"
    
    # --- Agent Instructions ---
    # Deep textual rules the coding agent reads before generation
    instructions: List[str] = field(
        default_factory=lambda: [
            "Inspect every imported mesh for 'Watertight' status.",
            "Ensure individual meshes cap at 20k triangles.",
            "Nest all assets inside the 'Main' Model container.",
            "Apply 'Natural' lighting for standard rendering.",
            "Decimate heavy props to avoid physics glitches."
        ]
    )
    
    def get_context(self) -> Dict[str, Any]:
        """
        Serializes the engine state into a dictionary for the 
        Goal to Game coding agent to parse.
        """
        return {
            "engine": self.name,
            "path": self.root_path,
            "format": self.hierarchy.get("primary_container", "Main"),
            "geometry": self.geometry_caps,
            "rules": self.instructions
        }

    def validate_mesh(self, mesh_name: str, tri_count: int) -> bool:
        """
        Logic hook for the agent to verify if a mesh meets Roblox standards.
        """
        return tri_count <= self.geometry_caps["max_triangulation"]

    def refine_scale(self, value: float) -> float:
        """
        Converts a Unity-style '1.0' to Roblox '100' if needed.
        """
        return value * self.geometry_caps["units_per_meter"]

# Instantiate the default configuration
Roblox = RobloxEngine()

# Export the object for easy access
__all__ = ["Roblox"]

if __name__ == "__main__":
    # Quick self-test
    print(f"Engine: {Roblox.name}")
    print(f"Path: {Roblox.root_path}")
    print(f"Geometry Limit: {Roblox.geometry_caps['max_triangulation']} tris")
```