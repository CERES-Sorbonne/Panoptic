// import { io } from 'socket.io-client'

// // Connect to your backend (adjust URL/port if needed)
// const socket = io('http://localhost:8000', {
//   query: {
//     userId: 'alice',
//     project: 'test123'
//   },
//   transports: ['websocket'] // optional: force WebSocket only
// })

// // Handle connection
// socket.on('connect', () => {
//   console.log('Connected to server')
//   console.log('Socket ID:', socket.id)
// })

// // Handle disconnect
// socket.on('disconnect', (reason) => {
//   console.log('Disconnected:', reason)
// })

// // Handle errors
// socket.on('connect_error', (err) => {
//   console.error('Connection error:', err.message)
// })

// // Example: handle custom event (if server emits one)
// socket.on('message', (data) => {
//   console.log('Received message:', data)
// })