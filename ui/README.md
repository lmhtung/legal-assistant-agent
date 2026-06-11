# MscAI Chat UI

UI chat tối giản viết bằng Next.js cho legal assistant backend.

## Chạy dev

```bash
cd ui
npm install
npm run dev
```

Mở `http://localhost:5173`.

Backend mặc định được gọi tại `http://localhost:8000`. Có thể đổi bằng file `.env.local`:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

UI gọi endpoint SSE `POST /api/v1/legal/chat/stream` để hiển thị luồng xử lý agent. Checkbox `Luồng` dùng để ẩn/hiện các status event ngay trong bubble trả lời.
