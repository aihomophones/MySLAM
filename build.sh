# Activate conda environment
source /home/crl/miniconda3/etc/profile.d/conda.sh
conda activate slam_env

# DBoW2
cd ./ORB-SLAM3/Thirdparty/DBoW2
mkdir build
cd build
cmake .. -DCMAKE_BUILD_TYPE=Release # add OpenCV_DIR definitions if needed, example:
#cmake .. -DCMAKE_BUILD_TYPE=Release -DOpenCV_DIR=/home/rapidlab/libs/opencv/lib/cmake/opencv4
make -j

cd ../../g2o

# g2o
mkdir build
cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j

cd ../../Sophus

# Sophus
mkdir build
cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j

# ORB_SLAM3
cd ../../../Vocabulary
echo "Uncompress vocabulary ..."
tar -xf ORBvoc.txt.tar.gz
cd ..

mkdir build
cd build
cmake .. -DCMAKE_BUILD_TYPE=Release # add OpenCV_DIR definitions if needed, example:
#cmake .. -DCMAKE_BUILD_TYPE=Release -DOpenCV_DIR=/home/rapidlab/libs/opencv/lib/cmake/opencv4
make -j8

# Photo-SLAM
echo "Building Photo-SLAM ..."
cd ../..
mkdir build
cd build
cmake .. -DTorch_DIR=/home/crl/miniconda3/envs/slam_env/lib/python3.12/site-packages/torch/share/cmake/Torch
make -j8
