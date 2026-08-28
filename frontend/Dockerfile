FROM node:22-alpine

WORKDIR /app

RUN corepack enable

# pnpm 10 对 ignored build scripts 返回非零退出码，用 --ignore-scripts 绕过
# （esbuild 二进制由 @esbuild/linux-* 可选依赖提供，vite 开发无需 postinstall）
COPY package.json ./
RUN pnpm install --ignore-scripts

COPY . .

EXPOSE 5173

CMD ["pnpm", "dev", "--host", "0.0.0.0"]
