#!/usr/bin/env node
const fs = require('fs')
const path = require('path')
const { spawn } = require('child_process')
const config = require('config')

// Ścieżka do pliku z procesami
const PID_FILE = path.join(process.cwd(), 'network-nodes.pid')

// Konfiguracja węzłów
const nodes = config.get('network.nodes')

// Funkcja do uruchamiania węzła
function startNode(nodeId) {
	console.log(`Starting node ${nodeId}...`)

	// Uruchom proces węzła
	const nodeProcess = spawn('node', ['src/blockchain/node.js', nodeId], {
		env: { ...process.env, NODE_ID: nodeId },
		stdio: 'pipe',
		detached: true,
	})

	// Zapisz PID do późniejszego zarządzania
	return nodeProcess.pid
}

// Funkcja do zatrzymywania węzłów
function stopNodes() {
	try {
		if (fs.existsSync(PID_FILE)) {
			const pids = JSON.parse(fs.readFileSync(PID_FILE, 'utf8'))

			pids.forEach(pid => {
				try {
					process.kill(pid, 'SIGINT')
					console.log(`Stopped process with PID ${pid}`)
				} catch (err) {
					console.log(`Process with PID ${pid} not found or already stopped`)
				}
			})

			// Usuń plik PID
			fs.unlinkSync(PID_FILE)
			console.log('All nodes stopped')
		} else {
			console.log('No running nodes found')
		}
	} catch (error) {
		console.error(`Error stopping nodes: ${error.message}`)
	}
}

// Główna funkcja do uruchamiania sieci
async function setupNetwork() {
	const command = process.argv[2]

	if (command === 'stop') {
		stopNodes()
		return
	}

	if (command === 'start' || !command) {
		// Sprawdź, czy sieć już działa
		if (fs.existsSync(PID_FILE)) {
			console.log('Network is already running. Stop it first with: npm run setup-network stop')
			return
		}

		console.log(`Starting blockchain network with ${nodes.length} nodes...`)

		// Uruchom wszystkie węzły
		const pids = []
		for (const node of nodes) {
			const pid = startNode(node.id)
			pids.push(pid)

			// Odczekaj chwilę między uruchomieniami węzłów
			await new Promise(resolve => setTimeout(resolve, 1000))
		}

		// Zapisz PID procesów
		fs.writeFileSync(PID_FILE, JSON.stringify(pids))

		console.log(`Network started with ${nodes.length} nodes. PIDs saved to ${PID_FILE}`)
		console.log('Use "npm run setup-network stop" to stop the network')
	} else {
		console.log('Unknown command. Use "start" or "stop"')
	}
}

// Uruchom skrypt
setupNetwork().catch(err => {
	console.error(`Error: ${err.message}`)
	process.exit(1)
})
