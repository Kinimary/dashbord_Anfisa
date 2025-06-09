/*
 * Конфигурационный файл для Arduino счетчика посетителей
 * Скопируйте этот файл как config.h в папку с Arduino скетчем
 */

#ifndef CONFIG_H
#define CONFIG_H

// WiFi настройки
#define WIFI_SSID "YOUR_WIFI_SSID"          // Замените на ваш WiFi SSID
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"   // Замените на ваш WiFi пароль

// Настройки сервера (замените IP на актуальный адрес вашего сервера)
#define SERVER_HOST "192.168.2.183"         // IP адрес сервера
#define SERVER_PORT 5000                    // Порт сервера

// Уникальный ID устройства (измените для каждого Arduino)
#define DEVICE_ID "ARDUINO_001"             // Уникальный ID для каждого устройства

// Настройки датчика (можете изменить по необходимости)
#define MEASUREMENT_INTERVAL 100            // Интервал измерений в миллисекундах
#define SEND_INTERVAL 60000                 // Интервал отправки данных в миллисекундах (60 сек)

// Пороги расстояния в сантиметрах
#define ZONE_THRESHOLD_CM 160               // Порог входа в зону
#define EXIT_THRESHOLD_CM 150               // Порог выхода из зоны
#define MIN_DISTANCE_CM 10                  // Минимальное расстояние для фильтрации шума

// Количество последовательных измерений для подтверждения
#define REQUIRED_CONSECUTIVE_MEASUREMENTS 3

// Пины для ультразвукового датчика
#define TRIG_PIN 3
#define ECHO_PIN 2

// Настройки времени
#define TIME_ZONE_OFFSET 3                  // Часовой пояс (UTC+3 для Минска)

// Настройки логирования (0 - минимум, 1 - базовый, 2 - подробный)
#define LOG_LEVEL 1

// Telegram настройки (опционально, пока не реализовано)
// #define TELEGRAM_BOT_TOKEN "YOUR_BOT_TOKEN"
// #define TELEGRAM_CHAT_ID "YOUR_CHAT_ID"

#endif