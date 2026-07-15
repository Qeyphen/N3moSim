import os
from glob import glob
from setuptools import find_packages, setup

package_name = "n3_sim"

setup(
    name=package_name,
    version="0.0.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        # launch files (yaml + py)
        (
            os.path.join("share", package_name, "launch"),
            glob("launch/*.yaml") + glob("launch/*.launch"),
        ),
    ],
    package_data={"": ["py.typed"]},
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Christophe Rousset",
    maintainer_email="c.rousset@pectum.fr",
    description="TODO: Package description",
    license="Copyright N3-MO - All right reserved",
    extras_require={
        "test": [
            "pytest",
        ],
    },
    entry_points={
        "console_scripts": [
            "anemo_sim = n3_sim.anemo_sim.anemo_sim_node:main",
            "simple_sim = n3_sim.simple_sim.simple_sim_node:main",
            "naveol_sim = n3_sim.naveol_sim.naveol_sim_node:main",
            "naveol_syd_sim = n3_sim.naveol_syd_sim.syd_node:main",
            "foxglove_converter = n3_sim.foxglove.foxglove_converter_node:main",
            "test_harness = n3_sim.simple_sim.test_harness_node:main",
            "joystick_node = n3_sim.joystick.joystick_node:main",
            "scenario_generator = n3_sim.scenario_generator.scenario_generator_node:main",
            "boat_traj_generator = n3_sim.boat_traj_generator.boat_traj_generator_node:main",
            "track_foxglove_converter = n3_sim.scenario_generator.track_foxglove_converter_node:main",
            "scenario_bridge = n3_sim.scenario_generator.scenario_bridge_node:main",
            "map_manager= n3_sim.scenario_generator.map_manager_node:main",
            "tracks_markers = n3_sim.scenario_generator.tracks_markers_node:main",
        ],
    },
)
