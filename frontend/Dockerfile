# --- 构建阶段 ---
FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .
# 生产环境 API 通过 nginx 反向代理，设置为相对路径
ENV VITE_API_BASE_URL=/api
RUN npm run build

# --- 运行阶段 ---
FROM nginx:alpine

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制 nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
