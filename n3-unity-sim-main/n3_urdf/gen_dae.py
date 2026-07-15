"""
Genere les fichiers .dae (Collada) pour le n3_urdf :
  - hull_main.dae    : flotteur principal (grand, babord)
  - hull_small.dae   : flotteur secondaire (petit, tribord)
  - sail.dae         : voile rigide profil NACA 0015
  - deck.dae         : plateforme centrale
  - crossbeam.dae    : barre transversale
  - rudder.dae       : safran (gouvernail) sur le flotteur principal
"""

import math
import os
import shutil

import numpy as np

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "meshes")
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------------------
# UTILITAIRES COLLADA
# ---------------------------------------------------------------------------


def vec3_to_str(verts):
    """Liste de (x,y,z) -> chaine float Collada."""
    return " ".join(f"{v:.6f}" for xyz in verts for v in xyz)


def normals_from_tris(verts, tris):
    """Calcule une normale par triangle."""
    norms = []
    for tri in tris:
        a = np.array(verts[tri[0]])
        b = np.array(verts[tri[1]])
        c = np.array(verts[tri[2]])
        n = np.cross(b - a, c - a)
        ln = np.linalg.norm(n)
        n = n / ln if ln > 1e-10 else np.array([0, 0, 1])
        norms.append(tuple(n))
    return norms


def collada_document(geom_id, geom_name, verts, tris, rgba=(0.3, 0.32, 0.36, 1.0)):
    """Genere un document Collada complet pour un maillage triangule."""

    norms = normals_from_tris(verts, tris)
    norm_flat = []
    for n in norms:
        norm_flat.extend([n, n, n])

    pos_str = vec3_to_str(verts)
    norm_str = vec3_to_str(norm_flat)

    p_list = []
    for i, tri in enumerate(tris):
        for j, vi in enumerate(tri):
            p_list.append(str(vi))
            p_list.append(str(i * 3 + j))
    p_str = " ".join(p_list)

    count = len(tris)
    nv = len(verts)
    nn = len(norm_flat)

    r, g, b, a = rgba

    dae = f"""<?xml version="1.0" encoding="utf-8"?>
<COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema" version="1.4.1">
  <asset>
    <created>2025-01-01</created>
    <modified>2025-01-01</modified>
    <unit name="meter" meter="1"/>
    <up_axis>Z_UP</up_axis>
  </asset>

  <library_effects>
    <effect id="{geom_id}_effect">
      <profile_COMMON>
        <technique sid="common">
          <phong>
            <emission><color>0 0 0 1</color></emission>
            <ambient><color>0.1 0.1 0.1 1</color></ambient>
            <diffuse><color>{r} {g} {b} {a}</color></diffuse>
            <specular><color>0.4 0.4 0.4 1</color></specular>
            <shininess><float>40</float></shininess>
          </phong>
        </technique>
      </profile_COMMON>
    </effect>
  </library_effects>

  <library_materials>
    <material id="{geom_id}_mat" name="{geom_id}_mat">
      <instance_effect url="#{geom_id}_effect"/>
    </material>
  </library_materials>

  <library_geometries>
    <geometry id="{geom_id}" name="{geom_name}">
      <mesh>
        <source id="{geom_id}-positions">
          <float_array id="{geom_id}-positions-array" count="{nv * 3}">
            {pos_str}
          </float_array>
          <technique_common>
            <accessor source="#{geom_id}-positions-array" count="{nv}" stride="3">
              <param name="X" type="float"/>
              <param name="Y" type="float"/>
              <param name="Z" type="float"/>
            </accessor>
          </technique_common>
        </source>

        <source id="{geom_id}-normals">
          <float_array id="{geom_id}-normals-array" count="{nn * 3}">
            {norm_str}
          </float_array>
          <technique_common>
            <accessor source="#{geom_id}-normals-array" count="{nn}" stride="3">
              <param name="X" type="float"/>
              <param name="Y" type="float"/>
              <param name="Z" type="float"/>
            </accessor>
          </technique_common>
        </source>

        <vertices id="{geom_id}-vertices">
          <input semantic="POSITION" source="#{geom_id}-positions"/>
        </vertices>

        <triangles count="{count}" material="{geom_id}_mat">
          <input semantic="VERTEX" source="#{geom_id}-vertices" offset="0"/>
          <input semantic="NORMAL" source="#{geom_id}-normals"  offset="1"/>
          <p>{p_str}</p>
        </triangles>
      </mesh>
    </geometry>
  </library_geometries>

  <library_visual_scenes>
    <visual_scene id="Scene" name="Scene">
      <node id="{geom_id}_node" name="{geom_name}" type="NODE">
        <instance_geometry url="#{geom_id}">
          <bind_material>
            <technique_common>
              <instance_material symbol="{geom_id}_mat"
                                 target="#{geom_id}_mat"/>
            </technique_common>
          </bind_material>
        </instance_geometry>
      </node>
    </visual_scene>
  </library_visual_scenes>

  <scene>
    <instance_visual_scene url="#Scene"/>
  </scene>
</COLLADA>
"""
    return dae


def collada_textured(
    geom_id, geom_name, verts, tris, uvs, texture_file, rgba=(0.8, 0.8, 0.8, 1.0)
):
    """Collada document with a diffuse texture map + base color fallback."""

    norms = normals_from_tris(verts, tris)
    norm_flat = []
    for n in norms:
        norm_flat.extend([n, n, n])

    pos_str = vec3_to_str(verts)
    norm_str = vec3_to_str(norm_flat)
    uv_str = " ".join(f"{u:.6f} {v:.6f}" for u, v in uvs)

    # Indices: pos, norm, uv per vertex per triangle
    p_list = []
    for i, tri in enumerate(tris):
        for j, vi in enumerate(tri):
            p_list.append(str(vi))  # position
            p_list.append(str(i * 3 + j))  # normal (flat)
            p_list.append(str(vi))  # uv (per-vertex)
    p_str = " ".join(p_list)

    count = len(tris)
    nv = len(verts)
    nn = len(norm_flat)
    r, g, b, a = rgba

    dae = f"""<?xml version="1.0" encoding="utf-8"?>
<COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema" version="1.4.1">
  <asset>
    <created>2025-01-01</created>
    <modified>2025-01-01</modified>
    <unit name="meter" meter="1"/>
    <up_axis>Z_UP</up_axis>
  </asset>

  <library_images>
    <image id="{geom_id}_img" name="{geom_id}_img">
      <init_from>{texture_file}</init_from>
    </image>
  </library_images>

  <library_effects>
    <effect id="{geom_id}_effect">
      <profile_COMMON>
        <newparam sid="{geom_id}_surface">
          <surface type="2D">
            <init_from>{geom_id}_img</init_from>
          </surface>
        </newparam>
        <newparam sid="{geom_id}_sampler">
          <sampler2D>
            <source>{geom_id}_surface</source>
            <minfilter>LINEAR</minfilter>
            <magfilter>LINEAR</magfilter>
          </sampler2D>
        </newparam>
        <technique sid="common">
          <phong>
            <emission><color>0 0 0 1</color></emission>
            <ambient><color>0.1 0.1 0.1 1</color></ambient>
            <diffuse>
              <texture texture="{geom_id}_sampler" texcoord="UVMap"/>
            </diffuse>
            <specular><color>0.3 0.3 0.3 1</color></specular>
            <shininess><float>30</float></shininess>
          </phong>
        </technique>
      </profile_COMMON>
    </effect>
  </library_effects>

  <library_materials>
    <material id="{geom_id}_mat" name="{geom_id}_mat">
      <instance_effect url="#{geom_id}_effect"/>
    </material>
  </library_materials>

  <library_geometries>
    <geometry id="{geom_id}" name="{geom_name}">
      <mesh>
        <source id="{geom_id}-positions">
          <float_array id="{geom_id}-positions-array" count="{nv * 3}">
            {pos_str}
          </float_array>
          <technique_common>
            <accessor source="#{geom_id}-positions-array" count="{nv}" stride="3">
              <param name="X" type="float"/>
              <param name="Y" type="float"/>
              <param name="Z" type="float"/>
            </accessor>
          </technique_common>
        </source>

        <source id="{geom_id}-normals">
          <float_array id="{geom_id}-normals-array" count="{nn * 3}">
            {norm_str}
          </float_array>
          <technique_common>
            <accessor source="#{geom_id}-normals-array" count="{nn}" stride="3">
              <param name="X" type="float"/>
              <param name="Y" type="float"/>
              <param name="Z" type="float"/>
            </accessor>
          </technique_common>
        </source>

        <source id="{geom_id}-uvs">
          <float_array id="{geom_id}-uvs-array" count="{nv * 2}">
            {uv_str}
          </float_array>
          <technique_common>
            <accessor source="#{geom_id}-uvs-array" count="{nv}" stride="2">
              <param name="S" type="float"/>
              <param name="T" type="float"/>
            </accessor>
          </technique_common>
        </source>

        <vertices id="{geom_id}-vertices">
          <input semantic="POSITION" source="#{geom_id}-positions"/>
        </vertices>

        <triangles count="{count}" material="{geom_id}_mat">
          <input semantic="VERTEX"   source="#{geom_id}-vertices" offset="0"/>
          <input semantic="NORMAL"   source="#{geom_id}-normals"  offset="1"/>
          <input semantic="TEXCOORD" source="#{geom_id}-uvs"      offset="2" set="0"/>
          <p>{p_str}</p>
        </triangles>
      </mesh>
    </geometry>
  </library_geometries>

  <library_visual_scenes>
    <visual_scene id="Scene" name="Scene">
      <node id="{geom_id}_node" name="{geom_name}" type="NODE">
        <instance_geometry url="#{geom_id}">
          <bind_material>
            <technique_common>
              <instance_material symbol="{geom_id}_mat"
                                 target="#{geom_id}_mat">
                <bind_vertex_input semantic="UVMap" input_semantic="TEXCOORD" input_set="0"/>
              </instance_material>
            </technique_common>
          </bind_material>
        </instance_geometry>
      </node>
    </visual_scene>
  </library_visual_scenes>

  <scene>
    <instance_visual_scene url="#Scene"/>
  </scene>
</COLLADA>
"""
    return dae


def save_dae(
    path,
    geom_id,
    geom_name,
    verts,
    tris,
    rgba=(0.3, 0.32, 0.36, 1.0),
    uvs=None,
    texture_file=None,
):
    if uvs is not None and texture_file is not None:
        content = collada_textured(
            geom_id, geom_name, verts, tris, uvs, texture_file, rgba
        )
    else:
        content = collada_document(geom_id, geom_name, verts, tris, rgba)
    with open(path, "w") as f:
        f.write(content)
    print(f"  {path}  ({len(verts)} verts, {len(tris)} tris)")


# ---------------------------------------------------------------------------
# HELPERS GEOMETRIE
# ---------------------------------------------------------------------------


def close_cap(verts, tris, ring_start, n, top=True):
    """Ferme une extremite (cap) en eventail depuis le centroide. Double-sided."""
    cx = sum(verts[ring_start + i][0] for i in range(n)) / n
    cy = sum(verts[ring_start + i][1] for i in range(n)) / n
    cz = sum(verts[ring_start + i][2] for i in range(n)) / n
    center_idx = len(verts)
    verts.append((cx, cy, cz))
    for i in range(n):
        i2 = (i + 1) % n
        a = ring_start + i
        b = ring_start + i2
        # Both windings for double-sided rendering
        tris.append((center_idx, a, b))
        tris.append((center_idx, b, a))


# ---------------------------------------------------------------------------
# 1. FLOTTEUR (HULL) - parametrable
# ---------------------------------------------------------------------------


def hull_cross_section(beam, height, n_bottom=16, n_top=4):
    """
    Closed cross-section: rounded bottom + flat deck on top.
    Returns a closed loop of (y, z) points.
    z=0 is the deck (top), z<0 is below waterline.
    """
    pts = []
    half_b = beam / 2
    depth = height * 0.7  # how deep the bottom goes

    # Bottom: half-ellipse from starboard to port (y = -half_b .. +half_b)
    for i in range(n_bottom + 1):
        theta = math.pi * i / n_bottom  # pi..0 so y goes -half_b..+half_b
        y = -half_b * math.cos(theta)
        z = -depth * math.sin(theta)
        pts.append((y, z))

    # Top deck: flat from port back to starboard (close the loop)
    for i in range(1, n_top):
        frac = i / n_top
        y = half_b - frac * beam  # +half_b .. -half_b
        pts.append((y, 0.0))

    return pts


def make_hull(length=6.225, beam=0.55, height=0.40, n_bottom=16, n_top=4, n_long=30):
    """
    Closed hull with rounded bottom and flat deck.
    Asymmetric taper: blunt bow and stern (no thin noses).
    """

    def taper(x_norm):
        """x_norm in [-1, 1]. Returns scale factor."""
        if x_norm >= 0:
            # Bow: smooth taper to 30%
            return 0.30 + 0.70 * (1.0 - x_norm**1.8)
        else:
            # Stern: broader, taper to 40%
            return 0.40 + 0.60 * (1.0 - abs(x_norm) ** 2.0)

    base = hull_cross_section(1.0, 1.0, n_bottom, n_top)
    n_ring = len(base)

    x_vals = np.linspace(-length / 2, length / 2, n_long)
    verts = []
    for x in x_vals:
        t = taper(2 * x / length)
        bw = beam * t
        bh = height * t
        for y0, z0 in base:
            verts.append((x, y0 * bw, z0 * bh))

    tris = []
    # Side walls (connect adjacent cross-sections)
    for ix in range(n_long - 1):
        for ip in range(n_ring):
            ip2 = (ip + 1) % n_ring  # wrap around (closed loop)
            a = ix * n_ring + ip
            b = ix * n_ring + ip2
            c = (ix + 1) * n_ring + ip
            d = (ix + 1) * n_ring + ip2
            tris.append((a, c, d))
            tris.append((a, d, b))

    # End caps (fan from center)
    # Bow cap (front, x = +length/2)
    bow_start = (n_long - 1) * n_ring
    close_cap(verts, tris, bow_start, n_ring, top=True)
    # Stern cap (back, x = -length/2)
    close_cap(verts, tris, 0, n_ring, top=False)

    return verts, tris


# ---------------------------------------------------------------------------
# 2. WING SAIL - profil NACA 0015
# ---------------------------------------------------------------------------


def sail_cross_section(chord, t_ratio=0.15, n=30, min_te=0.02):
    """
    Closed NACA-like airfoil cross-section as a proper closed loop.
    Leading edge at x=0 (will be placed at the mast).
    Trailing edge at x=-chord with minimum thickness min_te*chord.
    Returns list of (x, y) forming a closed polygon.
    """
    x_c = np.linspace(0, 1, n + 1)
    yt = (
        5
        * t_ratio
        * (
            0.2969 * np.sqrt(x_c)
            - 0.1260 * x_c
            - 0.3516 * x_c**2
            + 0.2843 * x_c**3
            - 0.1015 * x_c**4
        )
    )
    # Enforce minimum trailing edge thickness
    te_half = min_te / 2
    yt[-1] = te_half

    pts = []
    # Extrados: leading edge (x=0) to trailing edge (x=-chord)
    for i in range(n + 1):
        pts.append((-x_c[i] * chord, yt[i] * chord))
    # Intrados: trailing edge back to leading edge
    for i in range(n - 1, 0, -1):
        pts.append((-x_c[i] * chord, -yt[i] * chord))

    return pts


def make_sail(chord=3.830, height=4.5, t_ratio=0.15, n_profile=30, n_z=20):
    """
    Wing sail : closed NACA volume, extruded on Z.
    Leading edge vertical at x=0 (aligned with mast) for all Z.
    Taper only shrinks the chord toward trailing edge.
    """
    base = sail_cross_section(1.0, t_ratio, n_profile)
    n_pts = len(base)

    z_vals = np.linspace(0, height, n_z)
    tapers = np.linspace(1.0, 0.65, n_z)

    verts = []
    uvs = []
    for i, z in enumerate(z_vals):
        scale = tapers[i]
        for xp, yp in base:
            # xp is in [-1, 0]: leading edge at 0, trailing at -1
            # Scale chord by taper, keeping leading edge at x=0
            verts.append((xp * chord * scale, yp * chord * scale, z))
            # UV: approximate planar projection
            u = 1 + xp  # flipped: readable from starboard side
            uvs.append((u, z / height))

    tris = []
    # Side walls (closed loop: wrap with % n_pts)
    for iz in range(n_z - 1):
        for ip in range(n_pts):
            ip2 = (ip + 1) % n_pts
            a = iz * n_pts + ip
            b = iz * n_pts + ip2
            c = (iz + 1) * n_pts + ip
            d = (iz + 1) * n_pts + ip2
            tris.append((a, c, d))
            tris.append((a, d, b))

    # End caps
    close_cap(verts, tris, 0, n_pts, top=False)
    close_cap(verts, tris, (n_z - 1) * n_pts, n_pts, top=True)
    # UV for cap centers
    uvs.append((0.5, 0.0))
    uvs.append((0.5, 1.0))

    return verts, tris, uvs


# ---------------------------------------------------------------------------
# 3. PLATEFORME CENTRALE (deck)
# ---------------------------------------------------------------------------


def make_deck(length=2.80, width=2.50, height=0.06):
    """Pont central (box simple)."""
    hl, hw, hh = length / 2, width / 2, height / 2
    verts = [
        (-hl, -hw, -hh),
        (hl, -hw, -hh),
        (hl, hw, -hh),
        (-hl, hw, -hh),
        (-hl, -hw, hh),
        (hl, -hw, hh),
        (hl, hw, hh),
        (-hl, hw, hh),
    ]
    faces = [
        (0, 1, 2),
        (0, 2, 3),
        (4, 6, 5),
        (4, 7, 6),
        (0, 4, 5),
        (0, 5, 1),
        (2, 6, 7),
        (2, 7, 3),
        (1, 5, 6),
        (1, 6, 2),
        (0, 3, 7),
        (0, 7, 4),
    ]
    return verts, faces


# ---------------------------------------------------------------------------
# 4. BARRE TRANSVERSALE (crossbeam)
# ---------------------------------------------------------------------------


def make_crossbeam(length=3.5, section=0.12):
    """Barre transversale (profil carre, axe Y)."""
    hl = length / 2
    s = section / 2
    verts = [
        (-s, -hl, -s),
        (s, -hl, -s),
        (s, hl, -s),
        (-s, hl, -s),
        (-s, -hl, s),
        (s, -hl, s),
        (s, hl, s),
        (-s, hl, s),
    ]
    faces = [
        (0, 1, 2),
        (0, 2, 3),
        (4, 6, 5),
        (4, 7, 6),
        (0, 4, 5),
        (0, 5, 1),
        (2, 6, 7),
        (2, 7, 3),
        (1, 5, 6),
        (1, 6, 2),
        (0, 3, 7),
        (0, 7, 4),
    ]
    return verts, faces


# ---------------------------------------------------------------------------
# 5. SAFRAN (rudder) - volontairement surdimensionne pour la simu
# ---------------------------------------------------------------------------


def make_rudder(width=0.60, height=0.80, thickness=0.04):
    """
    Safran plat surdimensionne pour visibilite en simu.
    Joint at front top (origin at 0,0,0).
    Blade extends aft (-X) and down (-Z) from pivot.
    """
    ht = thickness / 2
    verts = [
        (-width, -ht, -height),
        (0, -ht, -height),
        (0, ht, -height),
        (-width, ht, -height),
        (-width, -ht, 0),
        (0, -ht, 0),
        (0, ht, 0),
        (-width, ht, 0),
    ]
    faces = [
        (0, 1, 2),
        (0, 2, 3),
        (4, 6, 5),
        (4, 7, 6),
        (0, 4, 5),
        (0, 5, 1),
        (2, 6, 7),
        (2, 7, 3),
        (1, 5, 6),
        (1, 6, 2),
        (0, 3, 7),
        (0, 7, 4),
    ]
    return verts, faces


# ---------------------------------------------------------------------------
# GENERATION
# ---------------------------------------------------------------------------

print("Generation des meshes n3_urdf...")

# Couleurs distinctives
HULL_MAIN_COLOR = (0.15, 0.25, 0.50, 1.0)  # bleu fonce
HULL_SMALL_COLOR = (0.20, 0.55, 0.70, 1.0)  # bleu clair / cyan
SAIL_COLOR = (0.85, 0.25, 0.20, 1.0)  # rouge vif
DECK_COLOR = (0.90, 0.55, 0.10, 1.0)  # orange
BEAM_COLOR = (0.90, 0.55, 0.10, 1.0)  # orange
RUDDER_COLOR = (0.90, 0.70, 0.10, 1.0)  # jaune/orange

# Flotteur principal (babord) - plus grand
v, t = make_hull(length=6.225, beam=0.55, height=0.45)
save_dae(f"{OUT}/hull_main.dae", "hull_main", "hull_main", v, t, rgba=HULL_MAIN_COLOR)

# Flotteur secondaire (tribord) - plus petit
v, t = make_hull(length=4.0, beam=0.40, height=0.30)
save_dae(
    f"{OUT}/hull_small.dae", "hull_small", "hull_small", v, t, rgba=HULL_SMALL_COLOR
)

# Sail (voile rigide NACA 0015, hauteur reduite, avec logo)
v, t, uv = make_sail(chord=3.830, height=4.5, t_ratio=0.15)
# Copy logo to meshes dir
logo_src = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "textures", "logo.png"
)
logo_dst = os.path.join(OUT, "logo.png")
if os.path.exists(logo_src):
    shutil.copy2(logo_src, logo_dst)
save_dae(
    f"{OUT}/sail.dae",
    "sail",
    "sail",
    v,
    t,
    rgba=SAIL_COLOR,
    uvs=uv,
    texture_file="logo.png",
)

# Deck (plateforme centrale, epaisseur visible)
v, t = make_deck(length=2.80, width=2.50, height=0.15)
save_dae(f"{OUT}/deck.dae", "deck", "deck", v, t, rgba=DECK_COLOR)

# Crossbeam (section epaisse)
v, t = make_crossbeam(length=3.5, section=0.15)
save_dae(f"{OUT}/crossbeam.dae", "crossbeam", "crossbeam", v, t, rgba=BEAM_COLOR)

# Arrow (triangle pointant vers l'avant, flat sur le pont)
arrow_verts = [
    (1.2, 0, 0),  # pointe avant
    (-0.8, -0.8, 0),  # arriere gauche
    (-0.8, 0.8, 0),  # arriere droit
    # duplicate avec leger offset Z pour double face
    (1.2, 0, 0.01),
    (-0.8, -0.8, 0.01),
    (-0.8, 0.8, 0.01),
]
arrow_tris = [
    (0, 1, 2),  # face dessus
    (5, 4, 3),  # face dessous
]
ARROW_COLOR = (0.90, 0.15, 0.10, 1.0)  # rouge
save_dae(
    f"{OUT}/arrow.dae", "arrow", "arrow", arrow_verts, arrow_tris, rgba=ARROW_COLOR
)

# Rudder (safran surdimensionne)
v, t = make_rudder(width=0.60, height=0.80, thickness=0.04)
save_dae(f"{OUT}/rudder.dae", "rudder", "rudder", v, t, rgba=RUDDER_COLOR)

print("\nTous les meshes generes :")
for f in sorted(os.listdir(OUT)):
    if f.endswith(".dae"):
        path = os.path.join(OUT, f)
        size = os.path.getsize(path)
        print(f"  {f:25s}  {size // 1024} Ko")
