-- Вспомогательные функции для извлечения и нормализации URL и ключей.
-- Аналог на Python: agent/src/agent/observer/normalize.py

-- Извлечение URL репозитория из аргументов git-команды
CREATE OR REPLACE FUNCTION extractRepoUrl AS (args) ->
    ifNull(
        extractAll(
            extractAll(args, '(?:git@|https?://|ssh://)[^\\s]+')[1],  -- первый URL-кандидат
            '(?:https?://|ssh://(?:[^@]+@)?|git@)[^\\s]+'              -- уточнить паттерн
        )[1],                                                          -- первое совпадение
        ''                                                             -- или пустую строку
    );

-- Нормализация URL репозитория
-- https://host/path.git  |  git@host:path.git (scp)  |  ssh://git@host/path.git
CREATE OR REPLACE FUNCTION normalizeRepoUrl AS (url) ->
    replaceRegexpAll(
        replaceRegexpAll(
            replaceRegexpAll(
                lower(trim(TRAILING '.' FROM url)),
                '^ssh://[^@]+@', 'https://'
            ),
            '^git@([^:]+):', 'https://\\1/'
        ),
        '\\.git$', ''
    );

-- Извлечение ключа БД из аргументов tool call
CREATE OR REPLACE FUNCTION extractDbKey AS (args) ->
    ifNull(
        extractAllGroupsHorizontal(args, '(?i)(?:host|server|endpoint)[=:]([\\w.-]+)')[1][1],
        ''
    );
