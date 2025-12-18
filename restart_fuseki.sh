#!/bin/bash
# Restart Fuseki with merged knowledge graph

# Stop existing Fuseki
pkill -f fuseki-server
sleep 2

# Start Fuseki with merged file
cd /Users/maxent/jena_fuseki
java -Xmx4G -jar fuseki-server.jar --file=/Users/maxent/src/SRS4Autism/knowledge_graph/world_model_complete.ttl /srs4autism > /Users/maxent/src/SRS4Autism/data/logs/fuseki.log 2>&1 &

echo "Fuseki started with PID: $!"
echo "Logs: /Users/maxent/src/SRS4Autism/data/logs/fuseki.log"
echo ""
echo "Waiting for Fuseki to start..."
sleep 5

# Test if it's working
curl -s http://localhost:3030 > /dev/null && echo "✅ Fuseki is running!" || echo "⚠️  Fuseki may still be starting..."


