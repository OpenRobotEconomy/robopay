FROM ros:humble

# Build tooling, a couple of ROS packages used by the demo, and Python dev tools.
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3-pip \
      python3-colcon-common-extensions \
      ros-humble-turtlesim \
      git \
    && rm -rf /var/lib/apt/lists/*

# Lint/test tooling. Real runtime deps (web3, eth-account, circle SDK) come later.
RUN pip3 install --no-cache-dir pytest ruff pre-commit

# Auto-source ROS + the workspace in interactive shells.
RUN echo "source /opt/ros/humble/setup.bash" >> /etc/bash.bashrc \
 && echo "[ -f /workspaces/robopay/install/setup.bash ] && source /workspaces/robopay/install/setup.bash" >> /etc/bash.bashrc
