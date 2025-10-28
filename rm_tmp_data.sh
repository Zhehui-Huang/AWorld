find . -name ".DS_Store" -delete
find . -name "__pycache__" -type d -exec rm -r {} +
find . -name ".idea" -type d -exec rm -r {} +
rm -rf /home/ethan/repo/AWorld/tmp/*
rm -rf /home/ethan/repo/AWorld/examples/gaia/logs/*
rm -rf /home/ethan/repo/AWorld/examples/gaia/agent_collections/logs/*

