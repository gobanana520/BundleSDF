#!/bin/bash

DOCKER_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PROJ_ROOT=$(dirname "$DOCKER_DIR")

CONTAINER_NAME="bundlesdf/devel"
CONTAINER_DISPLAY_NAME="bundlesdf"
CONTAINER_TAG="latest"

USER_NAME="my_user"
USER_ID=$(id -u)
GROUP_ID=$(id -g)

CONDA_ENV_NAME="bundlesdf"
CONDA_ENV_PATHON_VERSION="3.9"

CUDA_ARCH="6.0 6.1 7.0 7.5 8.0 8.6"

EIGEN_VERSION="3.4.0"
YAML_CPP_VERSION="0.7.0"
# PYBIND11_VERSION="2.10.0"
PYBIND11_VERSION="2.11.1"
# OPENCV_VERSION="3.4.15"
OPENCV_VERSION="3.4.20"
PCL_VERSION="1.10.1"

WORK_DIR="code"