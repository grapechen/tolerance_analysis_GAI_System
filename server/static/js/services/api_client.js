/**
 * api_client.js - 基礎 HTTP 請求封裝
 *
 * 提供 get / post 兩個方法，統一處理 JSON 序列化、錯誤解析。
 * 所有 API service 模組應透過此 client 發送請求。
 */

const ApiClient = (() => {
  const _baseUrl = '';   // 相對路徑，由 Flask 伺服器提供

  async function _request(method, url, body = null) {
    const options = {
      method,
      headers: { 'Content-Type': 'application/json' },
    };
    if (body !== null) {
      options.body = JSON.stringify(body);
    }

    const response = await fetch(_baseUrl + url, options);

    if (!response.ok) {
      let errMsg = `HTTP ${response.status}`;
      try {
        const err = await response.json();
        errMsg = err.msg || err.error || errMsg;
      } catch (_) {}
      throw new Error(errMsg);
    }

    return response.json();
  }

  return {
    get:  (url)        => _request('GET',  url),
    post: (url, body)  => _request('POST', url, body),
  };
})();
