import React, { useState, useEffect } from 'react';
import './App.css';

function App() {
  const [config, setConfig] = useState({
    api_key: '',
    secret_key: '',
    symbol: 'BTCUSDT',
    buy_quantity: 0.001,
    sell_quantity: 0.001,
    // NEW: Price ranges
    buy_price_min: 100,
    buy_price_max: 102,
    sell_price_min: 108,
    sell_price_max: 110,
    max_price_deviation: 0.05,
    min_competitor_size_usdt: 10.0
  });

  const [botStatus, setBotStatus] = useState({
    running: false,
    message: ''
  });

  const [logs, setLogs] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

  // Fetch bot status periodically with higher frequency for aggressive monitoring
  useEffect(() => {
    const interval = setInterval(fetchBotStatus, 1000); // Increased to 1 second
    return () => clearInterval(interval);
  }, []);

  const fetchBotStatus = async () => {
    try {
      const response = await fetch(`${backendUrl}/api/bot-status`);
      const status = await response.json();
      setBotStatus(status);
    } catch (error) {
      console.error('Error fetching bot status:', error);
    }
  };

  const addLog = (message, type = 'info') => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs(prev => [...prev.slice(-99), { timestamp, message, type }]);
  };

  const handleInputChange = (e) => {
    const { name, value, type } = e.target;
    setConfig(prev => ({
      ...prev,
      // Clean up whitespace from API keys and convert numbers
      [name]: type === 'number' ? parseFloat(value) : value.trim()
    }));
  };

  const validatePriceRanges = () => {
    if (config.buy_price_min >= config.buy_price_max) {
      addLog('❌ Минимальная цена покупки должна быть меньше максимальной', 'error');
      return false;
    }
    if (config.sell_price_min >= config.sell_price_max) {
      addLog('❌ Минимальная цена продажи должна быть меньше максимальной', 'error');
      return false;
    }
    if (config.buy_price_max >= config.sell_price_min) {
      addLog('❌ Диапазон покупки не должен пересекаться с диапазоном продажи', 'error');
      return false;
    }
    return true;
  };

  const startBot = async () => {
    if (!config.api_key || !config.secret_key) {
      addLog('Пожалуйста, введите API ключи', 'error');
      return;
    }

    if (!validatePriceRanges()) {
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetch(`${backendUrl}/api/start-bot`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(config)
      });

      const result = await response.json();
      
      if (response.ok) {
        addLog(`🚀 Бот запущен для пары ${config.symbol}`, 'success');
        addLog(`💰 Диапазон покупки: ${config.buy_price_min} - ${config.buy_price_max}`, 'success');
        addLog(`💸 Диапазон продажи: ${config.sell_price_min} - ${config.sell_price_max}`, 'success');
        await fetchBotStatus();
      } else {
        addLog(`❌ Ошибка запуска: ${result.detail}`, 'error');
      }
    } catch (error) {
      addLog(`🔌 Ошибка соединения: ${error.message}`, 'error');
    } finally {
      setIsLoading(false);
    }
  };

  const stopBot = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${backendUrl}/api/stop-bot`, {
        method: 'POST'
      });

      const result = await response.json();
      
      if (response.ok) {
        addLog('⏹️ Бот остановлен', 'success');
        await fetchBotStatus();
      } else {
        addLog(`❌ Ошибка остановки: ${result.detail}`, 'error');
      }
    } catch (error) {
      addLog(`🔌 Ошибка соединения: ${error.message}`, 'error');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="App">
      <div className="container">
        <header className="header">
          <h1>🤖 MEXC Trading Bot</h1>
          <p>Автоматический торговый бот с диапазонами цен</p>
          <div className="range-badge">
            <span>📊 ДИАПАЗОННАЯ ТОРГОВЛЯ</span>
            <small>Работает в заданных ценовых диапазонах</small>
          </div>
        </header>

        {/* Configuration Section */}
        <div className="config-section">
          <h2>⚙️ Настройки</h2>
          <div className="config-grid">
            <div className="config-group">
              <label>API Key:</label>
              <input
                type="password"
                name="api_key"
                value={config.api_key}
                onChange={handleInputChange}
                placeholder="Введите API ключ MEXC"
                className="input-field"
              />
            </div>

            <div className="config-group">
              <label>Secret Key:</label>
              <input
                type="password"
                name="secret_key"
                value={config.secret_key}
                onChange={handleInputChange}
                placeholder="Введите Secret ключ MEXC"
                className="input-field"
              />
            </div>

            <div className="config-group">
              <label>Валютная пара:</label>
              <input
                type="text"
                name="symbol"
                value={config.symbol}
                onChange={handleInputChange}
                placeholder="BTCUSDT"
                className="input-field"
              />
            </div>

            {/* NEW: Price Range Configuration */}
            <div className="config-group range-section">
              <h3>💰 Диапазон покупки</h3>
              
              <div className="range-inputs">
                <div className="range-input-group">
                  <label>Мин. цена покупки:</label>
                  <input
                    type="number"
                    name="buy_price_min"
                    value={config.buy_price_min}
                    onChange={handleInputChange}
                    step="0.01"
                    min="0.01"
                    className="input-field range-input"
                    placeholder="100"
                  />
                </div>
                
                <div className="range-input-group">
                  <label>Макс. цена покупки:</label>
                  <input
                    type="number"
                    name="buy_price_max"
                    value={config.buy_price_max}
                    onChange={handleInputChange}
                    step="0.01"
                    min="0.01"
                    className="input-field range-input"
                    placeholder="102"
                  />
                </div>
              </div>
              
              <div className="range-info">
                <small>🎯 Бот будет покупать только в диапазоне {config.buy_price_min} - {config.buy_price_max}</small>
              </div>
            </div>

            <div className="config-group range-section">
              <h3>💸 Диапазон продажи</h3>
              
              <div className="range-inputs">
                <div className="range-input-group">
                  <label>Мин. цена продажи:</label>
                  <input
                    type="number"
                    name="sell_price_min"
                    value={config.sell_price_min}
                    onChange={handleInputChange}
                    step="0.01"
                    min="0.01"
                    className="input-field range-input"
                    placeholder="108"
                  />
                </div>
                
                <div className="range-input-group">
                  <label>Макс. цена продажи:</label>
                  <input
                    type="number"
                    name="sell_price_max"
                    value={config.sell_price_max}
                    onChange={handleInputChange}
                    step="0.01"
                    min="0.01"
                    className="input-field range-input"
                    placeholder="110"
                  />
                </div>
              </div>
              
              <div className="range-info">
                <small>🎯 Бот будет продавать только в диапазоне {config.sell_price_min} - {config.sell_price_max}</small>
              </div>
            </div>

            <div className="config-group">
              <label>Количество на покупку:</label>
              <input
                type="number"
                name="buy_quantity"
                value={config.buy_quantity}
                onChange={handleInputChange}
                step="0.001"
                min="0.001"
                className="input-field"
              />
            </div>

            <div className="config-group">
              <label>Количество на продажу:</label>
              <input
                type="number"
                name="sell_quantity"
                value={config.sell_quantity}
                onChange={handleInputChange}
                step="0.001"
                min="0.001"
                className="input-field"
              />
            </div>

            <div className="config-group">
              <label>Мин. сумма конкурента для перебивания ($):</label>
              <input
                type="number"
                name="min_competitor_size_usdt"
                value={config.min_competitor_size_usdt}
                onChange={handleInputChange}
                step="1"
                min="1"
                max="1000"
                className="input-field"
                placeholder="10"
              />
              <small style={{color: '#666', fontSize: '0.8rem', marginTop: '4px'}}>
                💡 Не перебивать заказы меньше этой суммы - пусть исполнятся сами
              </small>
            </div>
          </div>

          {/* Price Range Visualization */}
          <div className="range-visualization">
            <h3>📊 Визуализация диапазонов</h3>
            <div className="range-chart">
              <div className="range-bar buy-range">
                <span className="range-label">Покупка: {config.buy_price_min} - {config.buy_price_max}</span>
              </div>
              <div className="range-gap">
                <span className="gap-info">Зазор: {(config.sell_price_min - config.buy_price_max).toFixed(2)}</span>
              </div>
              <div className="range-bar sell-range">
                <span className="range-label">Продажа: {config.sell_price_min} - {config.sell_price_max}</span>
              </div>
            </div>
          </div>

          <div className="button-group">
            <button
              onClick={startBot}
              disabled={isLoading || botStatus.running}
              className="btn btn-start"
            >
              {isLoading ? '⏳ Запуск...' : '▶️ Запустить бота'}
            </button>

            <button
              onClick={stopBot}
              disabled={isLoading || !botStatus.running}
              className="btn btn-stop"
            >
              {isLoading ? '⏳ Остановка...' : '⏹️ Остановить бота'}
            </button>
          </div>
        </div>

        {/* Status Section */}
        <div className="status-section">
          <h2>📊 Статус бота</h2>
          <div className="status-grid">
            <div className="status-item">
              <span className="status-label">Состояние:</span>
              <span className={`status-value ${botStatus.running ? 'running' : 'stopped'}`}>
                {botStatus.running ? '🟢 Работает (ДИАПАЗОННО)' : '🔴 Остановлен'}
              </span>
            </div>

            {botStatus.symbol && (
              <div className="status-item">
                <span className="status-label">Пара:</span>
                <span className="status-value">{botStatus.symbol}</span>
              </div>
            )}

            {/* NEW: Display current price ranges */}
            {botStatus.buy_range && (
              <div className="status-item">
                <span className="status-label">Диапазон покупки:</span>
                <span className="status-value buy-range-indicator">
                  💰 {botStatus.buy_range.min} - {botStatus.buy_range.max}
                </span>
              </div>
            )}

            {botStatus.sell_range && (
              <div className="status-item">
                <span className="status-label">Диапазон продажи:</span>
                <span className="status-value sell-range-indicator">
                  💸 {botStatus.sell_range.min} - {botStatus.sell_range.max}
                </span>
              </div>
            )}

            {botStatus.min_competitor_size_usdt && (
              <div className="status-item">
                <span className="status-label">Мин. размер конкурента:</span>
                <span className="status-value smart">${botStatus.min_competitor_size_usdt}</span>
              </div>
            )}

            {botStatus.update_frequency && (
              <div className="status-item">
                <span className="status-label">Частота обновлений:</span>
                <span className="status-value aggressive">⚡ {botStatus.update_frequency}</span>
              </div>
            )}

            {botStatus.best_bid && (
              <div className="status-item">
                <span className="status-label">Лучшая покупка:</span>
                <span className="status-value">{botStatus.best_bid}</span>
              </div>
            )}

            {botStatus.best_ask && (
              <div className="status-item">
                <span className="status-label">Лучшая продажа:</span>
                <span className="status-value">{botStatus.best_ask}</span>
              </div>
            )}

            {botStatus.spread && (
              <div className="status-item">
                <span className="status-label">Спред:</span>
                <span className="status-value">{botStatus.spread}</span>
              </div>
            )}

            {botStatus.initial_price && (
              <div className="status-item">
                <span className="status-label">Начальная цена:</span>
                <span className="status-value">{botStatus.initial_price}</span>
              </div>
            )}

            {botStatus.orderbook_depth && (
              <div className="status-item">
                <span className="status-label">Глубина стакана:</span>
                <span className="status-value">
                  📈 {botStatus.orderbook_depth.bids_count} bids |
                  📉 {botStatus.orderbook_depth.asks_count} asks
                </span>
              </div>
            )}
          </div>

          {/* Active Orders with Range Information */}
          {(botStatus.current_buy_order || botStatus.current_sell_order) && (
            <div className="orders-section">
              <h3>⚔️ Активные ордера (В диапазоне цен)</h3>

              {botStatus.current_buy_order && (
                <div className="order-item buy-order range-based">
                  <strong>🟢 ПОКУПКА В ДИАПАЗОНЕ:</strong>
                  <span>Цена: {botStatus.current_buy_order.price}</span>
                  <span>ID: {botStatus.current_buy_order.orderId}</span>
                  <span className="range-indicator">
                    📊 Диапазон: {botStatus.buy_range?.min} - {botStatus.buy_range?.max}
                  </span>
                </div>
              )}

              {botStatus.current_sell_order && (
                <div className="order-item sell-order range-based">
                  <strong>🔴 ПРОДАЖА В ДИАПАЗОНЕ:</strong>
                  <span>Цена: {botStatus.current_sell_order.price}</span>
                  <span>ID: {botStatus.current_sell_order.orderId}</span>
                  <span className="range-indicator">
                    📊 Диапазон: {botStatus.sell_range?.min} - {botStatus.sell_range?.max}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Logs Section */}
        <div className="logs-section">
          <h2>📝 Журнал событий</h2>
          <div className="logs-container">
            {logs.length === 0 ? (
              <p className="no-logs">Журнал пуст</p>
            ) : (
              logs.map((log, index) => (
                <div key={index} className={`log-item ${log.type}`}>
                  <span className="log-time">{log.timestamp}</span>
                  <span className="log-message">{log.message}</span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Help Section */}
        <div className="help-section">
          <h2>ℹ️ Инструкция по диапазонной торговле</h2>
          <div className="help-content">
            <ol>
              <li>Получите API ключи в личном кабинете MEXC (разрешения: торговля)</li>
              <li>Введите API ключи и настройки торговли</li>
              <li>Выберите валютную пару в формате XXXUSDT</li>
              <li>
                <strong>Настройте диапазоны цен:</strong>
                <ul>
                  <li>💰 Диапазон покупки (например, 100-102): бот будет покупать только в этом диапазоне</li>
                  <li>💸 Диапазон продажи (например, 108-110): бот будет продавать только в этом диапазоне</li>
                  <li>⚠️ Диапазоны не должны пересекаться!</li>
                </ul>
              </li>
              <li>Установите размеры ордеров и минимальный размер конкурента</li>
              <li>Нажмите "Запустить бота" для начала диапазонной торговли</li>
            </ol>

            <div className="range-features">
              <h4>📊 Особенности диапазонной торговли:</h4>
              <ul>
                <li>🎯 Четкое ограничение цен покупки и продажи</li>
                <li>⚔️ Перебивание конкурентов только внутри диапазонов</li>
                <li>🚀 Высокая частота обновлений (100ms)</li>
                <li>🔄 Автоматическое удержание позиций в диапазонах</li>
                <li>📈 Профессиональная алгоритмическая торговля</li>
                <li>💡 Игнорирование мелких конкурентов (настраивается)</li>
              </ul>
            </div>

            <div className="warning">
              <strong>⚠️ Внимание:</strong> Диапазонная торговля криптовалютами связана с высокими рисками.
              Используйте только те средства, потерю которых можете себе позволить.
              Убедитесь, что диапазоны настроены корректно и не пересекаются.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;