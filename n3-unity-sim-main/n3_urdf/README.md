# N3mo_v2 – Package ROS2 URDF

Modèle URDF du catamaran autonome **N3mo_v2** à voile rigide (wing sail).

## Dimensions (depuis plans CAO)

| Cote         | Valeur  | Description                        |
|--------------|---------|------------------------------------|
| `6225`       | 6.225 m | Longueur des flotteurs             |
| `7996`       | 7.996 m | Envergure totale (hors-tout Y)     |
| `4459`       | 4.459 m | Longueur hors-tout du hull (X)     |
| `3500`       | 3.500 m | Entreaxe des deux flotteurs        |
| `3830`       | 3.830 m | Corde de la wing sail              |
| `2852`       | 2.852 m | Section de profil visible          |
| *(estimé)*   | ~9.0 m  | Hauteur totale de la wing sail     |

## Arbre de liens

```
base_link  (plateforme centrale / pont)
├── hull_port_link        [fixed] ← flotteur bâbord
├── hull_stbd_link        [fixed] ← flotteur tribord
├── crossbeam_fwd_link    [fixed] ← barre avant
├── crossbeam_aft_link    [fixed] ← barre arrière
└── mast_link             [fixed] ← pied de mât
    └── sail_link         [continuous / Z] ← wing sail
```

Le joint `sail_joint` est **continu** : la voile pivote autour de l'axe Z.

## Lancement

```bash
# Copier dans le workspace
cp -r n3_urdf ~/ros2_ws/src/

# Build
cd ~/ros2_ws
colcon build --packages-select n3_urdf
source install/setup.bash

# Visualiser avec slider de contrôle de la voile
ros2 launch n3_urdf display.launch.py use_gui:=true
```

## Générer le URDF brut

```bash
ros2 run xacro xacro urdf/n3_urdf.urdf.xacro > n3_urdf_full.urdf
# Vérifier
check_urdf n3_urdf_full.urdf
```

## Contrôler la voile en ligne de commande

```bash
# Piloter l'angle de la voile (en radians)
ros2 topic pub /joint_states sensor_msgs/msg/JointState \
  '{header: {stamp: {sec: 0}}, name: ["sail_joint"], position: [0.5], velocity: [0.0], effort: [0.0]}'
```

## Ajouter des meshes Blender (.dae)

1. Modéliser les formes dans Blender (NACA pour la voile, coques effilées)
2. Exporter en `.dae` avec textures embarquées
3. Déposer dans `meshes/` et `textures/`
4. Remplacer les `<box>` / `<cylinder>` du xacro par :

```xml
<geometry>
  <mesh filename="package://n3_urdf/meshes/hull_port.dae"/>
</geometry>
```

## Topics ROS2

| Topic               | Type                       | Rôle                    |
|---------------------|----------------------------|-------------------------|
| `/robot_description`| `std_msgs/String`          | URDF publié             |
| `/joint_states`     | `sensor_msgs/JointState`   | Angle voile             |
| `/tf`               | `tf2_msgs/TFMessage`       | Arbre des transforms    |
| `/tf_static`        | `tf2_msgs/TFMessage`       | Joints fixes            |
