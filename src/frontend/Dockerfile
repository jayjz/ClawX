# Use Node.js LTS (Alpine for smaller size)
FROM node:20-alpine

# Set working directory inside the container
WORKDIR /app

# Copy package configs first (optimizes cache)
COPY package.json package-lock.json ./

# Install dependencies
RUN npm install

# Copy the source code
COPY . .

# Expose the Vite port
EXPOSE 5173

# Start the dev server, binding to 0.0.0.0 so the host can see it
CMD ["npm", "run", "dev", "--", "--host"]
