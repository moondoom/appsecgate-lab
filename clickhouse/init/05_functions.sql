-- Вспомогательные функции для извлечения и нормализации URL и ключей.
-- Аналог на Python: agent/src/agent/observer/normalize.py

-- Извлечение URL репозитория из аргументов git-команды
CREATE OR REPLACE FUNCTION extractRepoUrl AS (args) ->
    extractAll(
        extractAll(args, '(?:git@|https?://|ssh://)[^\\s]+'),  -- сначала найти что-то похожее на URL
        '(?:https?://|ssh://(?:[^@]+@)?|git@)[^\\s]+'          -- уточнить паттерн
    )[1] ?? '';                                                 -- взять первое совпадение или пустую строку

-- Нормализация URL репозитория
CREATE OR REPLACE FUNCTION normalizeRepoUrl AS (url) ->
    replaceRegexpAll(
        replaceRegexpAll(
            lowerASCII(trim(TRAILING '.' FROM replaceAll(url, 'git@', 'https://'))),
            '\\.git$', ''
        ),
        '^ssh://[^@]+@', 'https://'
    );

-- Извлечение ключа БД из аргументов tool call
CREATE OR REPLACE FUNCTION extractDbKey AS (args) ->
    extractAll(
        extractAll(args, '(?:host|server|endpoint)[=:][\\w.-]+'), -- найти host/server/endpoint
        '(?i)(?:host|server|endpoint)[=:]([\\w.-]+)'              -- захватить значение
    )[1] ?? '';
