const { createCanvas } = require('canvas');
const fs = require('fs');
const path = require('path');

function generateIcon(size, fileName) {
    const canvas = createCanvas(size, size);
    const ctx = canvas.getContext('2d');

    // Background: Dark Slate
    ctx.fillStyle = '#0f172a';
    ctx.fillRect(0, 0, size, size);

    // Text: white "FD"
    ctx.fillStyle = 'white';
    ctx.font = `bold ${Math.floor(size * 0.4)}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('FD', size / 2, size / 2);

    // Ensure directory exists
    const dir = path.join(__dirname, '..', 'frontend', 'public', 'icons');
    if (!fs.existsSync(dir)){
        fs.mkdirSync(dir, { recursive: true });
    }

    const buffer = canvas.toBuffer('image/png');
    const filePath = path.join(dir, fileName);
    fs.writeFileSync(filePath, buffer);
    console.log(`Generated: ${filePath}`);
}

generateIcon(192, 'icon-192.png');
generateIcon(512, 'icon-512.png');
