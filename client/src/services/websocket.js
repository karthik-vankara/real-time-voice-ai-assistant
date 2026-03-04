export class WebSocketClient {
    constructor(url, config = {}) {
        Object.defineProperty(this, "ws", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: null
        });
        Object.defineProperty(this, "url", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: void 0
        });
        Object.defineProperty(this, "config", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: void 0
        });
        Object.defineProperty(this, "reconnectAttempts", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: 0
        });
        Object.defineProperty(this, "maxReconnectAttempts", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: 5
        });
        Object.defineProperty(this, "reconnectDelay", {
            enumerable: true,
            configurable: true,
            writable: true,
            value: 3000
        });
        this.url = url;
        this.config = config;
    }
    connect() {
        return new Promise((resolve, reject) => {
            try {
                this.ws = new WebSocket(this.url);
                this.ws.onopen = () => {
                    console.log('WebSocket connected');
                    this.reconnectAttempts = 0;
                    this.config.onConnect?.();
                    resolve();
                };
                this.ws.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        this.config.onMessage?.(data);
                    }
                    catch (error) {
                        console.error('Failed to parse message:', error);
                    }
                };
                this.ws.onerror = (error) => {
                    console.error('WebSocket error:', error);
                    this.config.onError?.(new Error('WebSocket error'));
                    reject(new Error('WebSocket connection failed'));
                };
                this.ws.onclose = () => {
                    console.log('WebSocket disconnected');
                    this.config.onDisconnect?.();
                    this.attemptReconnect();
                };
            }
            catch (error) {
                reject(error);
            }
        });
    }
    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
            setTimeout(() => {
                this.connect().catch((error) => {
                    console.error('Reconnection failed:', error);
                });
            }, this.reconnectDelay);
        }
    }
    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }
    sendAudio(audioData) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(audioData);
        }
        else {
            console.warn('WebSocket is not connected');
        }
    }
    isConnected() {
        return this.ws?.readyState === WebSocket.OPEN;
    }
}
