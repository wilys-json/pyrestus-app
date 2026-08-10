#!/bin/bash

# Install & setup Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install.sh)"
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> $HOME/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"

# Install Anaconda
brew install --cask anaconda
echo 'eval "export PATH="/usr/local/anaconda3/bin:$(PATH)"' >> $HOME/.zshrc

# Install Dependencies
conda env create -f environment.yml

# Activate environment
eval "$(conda shell.bash hook)"
conda activate pyrestus

# Setup
python3 -m setup build_ext --inplace -q
