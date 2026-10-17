"""
Клиент SampleAPIs Coffee.

Создание напитка:
POST https://api.sampleapis.com/coffee/hot

Заголовки:
Content-Type: application/json — формат отправляемого тела.
Accept: application/json — ожидаемый формат ответа.

Поля тела:
title - строка, название;
description - строка, описание;
ingredients - список строк, ингредиенты;
image - строка, адрес изображения.

В нашем сценарии передаются все четыре поля.
Обязательность полей на сервере отдельно не проверялась.
Расширенная локальная проверка входных полей не реализована.

id при создании не отправляем: получаем его от сервера.
Ожидаем HTTP 201 или 200 и JSON-объект созданного напитка с id.
Фактические статусы программа выводит при запуске.
"""

from typing import Any
from uuid import uuid4

import requests


JsonObject = dict[str, object]


class CoffeeApiError(Exception):
    pass


class CoffeeNotFoundError(CoffeeApiError):
    pass


class SampleApisCoffeeClient:
    def __init__(
        self,
        base_url: str = "https://api.sampleapis.com/coffee/hot",
        timeout: float = 10.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def list_drinks(self) -> list[JsonObject]:
        response = self._request("GET")
        data = self._get_json(response)

        if not isinstance(data, list):
            raise CoffeeApiError("Ожидался список напитков")

        for drink in data:
            if not isinstance(drink, dict):
                raise CoffeeApiError(
                    "Каждый напиток должен быть JSON-объектом"
                )

        return data

    def get_drink(self, drink_id: int) -> JsonObject:
        path = self._path(drink_id)
        response = self._request("GET", path)
        data = self._get_json(response)

        if not isinstance(data, dict):
            raise CoffeeApiError("Ожидался JSON-объект напитка")

        return data

    def create_drink(self, payload: JsonObject) -> JsonObject:
        response = self._request("POST", payload=payload)
        data = self._get_json(response)

        if not isinstance(data, dict):
            raise CoffeeApiError(
                "После POST ожидался JSON-объект созданного напитка"
            )

        if "id" not in data:
            raise CoffeeApiError(
                "После POST сервер не вернул поле id"
            )

        return data

    def replace_drink(
        self,
        drink_id: int,
        payload: JsonObject,
    ) -> JsonObject:
        path = self._path(drink_id)
        response = self._request("PUT", path, payload)
        data = self._get_json(response)

        if not isinstance(data, dict):
            raise CoffeeApiError(
                "После PUT ожидался JSON-объект напитка"
            )

        return data

    def update_drink(
        self,
        drink_id: int,
        changes: JsonObject,
    ) -> JsonObject:
        path = self._path(drink_id)
        response = self._request("PATCH", path, changes)
        data = self._get_json(response)

        if not isinstance(data, dict):
            raise CoffeeApiError(
                "После PATCH ожидался JSON-объект напитка"
            )

        return data

    def delete_drink(self, drink_id: int) -> None:
        path = self._path(drink_id)
        self._request("DELETE", path)

    def _path(self, drink_id: int) -> str:
        if type(drink_id) is not int or drink_id <= 0:
            raise ValueError(
                "id должен быть положительным целым числом"
            )

        return f"/{drink_id}"

    def _request(
        self,
        method: str,
        path: str = "",
        payload: JsonObject | None = None,
    ) -> requests.Response:
        url = self._base_url + path

        try:
            response = requests.request(
                method=method,
                url=url,
                json=payload,
                headers={"Accept": "application/json"},
                timeout=self._timeout,
                allow_redirects=False,
            )
        except requests.exceptions.Timeout as error:
            raise CoffeeApiError(
                f"Тайм-аут при {method} {url}"
            ) from error
        except requests.exceptions.RequestException as error:
            raise CoffeeApiError(
                f"Сетевая ошибка при {method} {url}: {error}"
            ) from error

        print(f"  {method} {url} -> HTTP {response.status_code}")

        if response.status_code == 404:
            raise CoffeeNotFoundError(
                f"Ресурс не найден: {method} {url}"
            )

        expected_statuses = {
            "GET": {200},
            "POST": {200, 201},
            "PUT": {200},
            "PATCH": {200},
            "DELETE": {200, 204},
        }

        if response.status_code not in expected_statuses[method]:
            raise CoffeeApiError(
                f"Неожиданный HTTP {response.status_code} "
                f"при {method} {url}. "
                f"Тело ответа: {response.text[:200]!r}"
            )

        return response

    def _get_json(self, response: requests.Response) -> Any:
        if response.status_code == 204 or not response.content.strip():
            raise CoffeeApiError(
                "Ожидался JSON, но тело ответа пустое"
            )

        content_type = (
            response.headers.get("Content-Type", "")
            .split(";", 1)[0]
            .strip()
            .lower()
        )

        is_json = (
            content_type == "application/json"
            or (
                content_type.startswith("application/")
                and content_type.endswith("+json")
            )
        )

        if not is_json:
            raise CoffeeApiError(
                f"Ожидался JSON, но сервер вернул "
                f"Content-Type: {content_type!r}. "
                f"Тело ответа: {response.text[:100]!r}"
            )

        try:
            return response.json()
        except ValueError as error:
            raise CoffeeApiError(
                f"Не удалось разобрать JSON: {error}"
            ) from error


def check_fields(
    expected: JsonObject,
    actual: JsonObject,
    stage: str,
) -> None:
    problems: list[str] = []

    for key, expected_value in expected.items():
        if key not in actual:
            problems.append(f"поле '{key}' отсутствует в ответе")
            continue

        actual_value = actual[key]

        if actual_value != expected_value:
            problems.append(
                f"поле '{key}': ожидали {expected_value!r}, "
                f"получили {actual_value!r}"
            )

    if problems:
        raise ValueError(f"{stage}: " + "; ".join(problems))

    print(f"  {stage}: все проверяемые поля совпадают")


def main() -> int:
    client = SampleApisCoffeeClient()
    marker = uuid4().hex[:8]
    created_id = None

    print(f"Метка группы: {marker}")
    print("Сохраните метку для ручной проверки при ошибке POST")

    try:
        drinks = client.list_drinks()
        print(f"[1/8] GET список: получено напитков: {len(drinks)}")

        payload: JsonObject = {
            "title": f"Group coffee {marker}",
            "description": "Горячий кофе, созданный клиентом группы",
            "ingredients": ["Espresso", "Water"],
            "image": "https://example.com/coffee.jpg",
        }

        try:
            created = client.create_drink(payload)
        except CoffeeApiError:
            print(
                "[2/8] Создание не подтверждено. "
                "Если сервер успел создать запись, её id неизвестен. "
                f"Не повторяйте POST вслепую: проверьте метку {marker}"
            )
            raise

        new_id = created.get("id")

        if type(new_id) is not int or new_id <= 0:
            raise ValueError(
                f"POST вернул некорректный id: {new_id!r}. "
                "Запись могла создаться. "
                f"Проверьте каталог вручную по метке {marker}"
            )

        created_id = new_id
        print(f"[2/8] POST создан: id={created_id}")

        drink = client.get_drink(created_id)
        check_fields(
            {**payload, "id": created_id},
            drink,
            "[3/8] GET после POST",
        )

        new_payload: JsonObject = {
            "title": f"Group latte {marker}",
            "description": "Полностью заменено через PUT",
            "ingredients": ["Espresso", "Milk"],
            "image": "https://example.com/latte.jpg",
        }

        client.replace_drink(created_id, new_payload)
        print(f"[4/8] PUT id={created_id}: запрос выполнен")

        before_patch = client.get_drink(created_id)
        check_fields(
            {**new_payload, "id": created_id},
            before_patch,
            "[5/8] GET после PUT",
        )

        changes: JsonObject = {
            "description": "Изменено через PATCH"
        }

        client.update_drink(created_id, changes)
        drink = client.get_drink(created_id)

        check_fields(
            {**before_patch, **changes},
            drink,
            "[6/8] GET после PATCH",
        )

        client.delete_drink(created_id)
        print(f"[7/8] DELETE id={created_id}: запрос выполнен")

        try:
            client.get_drink(created_id)
        except CoffeeNotFoundError:
            print(
                f"[8/8] GET id={created_id}: "
                "ожидаемый 404, запись удалена"
            )
            created_id = None
        else:
            raise ValueError(
                f"Запись id={created_id} существует после DELETE"
            )

        print("Сценарий выполнен успешно")

    except (CoffeeApiError, ValueError) as error:
        print(f"Ошибка: {error}. Метка группы: {marker}")
        return 1

    finally:
        if created_id is not None:
            print(f"Очистка: пытаемся удалить id={created_id}")

            try:
                client.delete_drink(created_id)
                print("Запрос очистки выполнен")
            except CoffeeNotFoundError:
                print("Запись уже отсутствует")
            except CoffeeApiError as error:
                print(
                    f"Не удалось удалить id={created_id}: {error}. "
                    f"Метка группы: {marker}"
                )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())