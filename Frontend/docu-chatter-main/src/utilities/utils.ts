export const fileToBase64 = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.readAsDataURL(file);

    reader.onload = () => {
      resolve(reader.result as string);  // <-- cast to string
    };

    reader.onerror = (error) => reject(error);
  });
};

export const generateUUID = (): string => {
  // Use crypto.getRandomValues if available (Web Crypto API)
  if (typeof window !== 'undefined' && window.crypto && window.crypto.getRandomValues) {
    const arr = new Uint8Array(16);
    crypto.getRandomValues(arr);
    // Set version 4
    arr[6] = (arr[6] & 0x0f) | 0x40;
    arr[8] = (arr[8] & 0x3f) | 0x80;
    
    const hexString = Array.from(arr)
      .map(b => b.toString(16).padStart(2, '0'))
      .join('');
    
    return `${hexString.slice(0, 8)}-${hexString.slice(8, 12)}-${hexString.slice(12, 16)}-${hexString.slice(16, 20)}-${hexString.slice(20)}`;
  }
  
  // Fallback implementation
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
};