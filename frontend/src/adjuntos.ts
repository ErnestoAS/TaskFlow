/**
 * Adjuntos (Etapa 3.8, §4.4): las fotos se reducen aquí antes de subirlas (lado mayor 2000 px,
 * calidad 0.8), así el límite de 10 MB cuenta sobre lo ya reducido y no se gastan los datos del
 * teléfono. Si la versión reducida sale más grande, se sube la original. Los PDF los comprime el
 * servidor; lo demás se sube tal cual.
 */

const LADO_MAXIMO = 2000;
const CALIDAD = 0.8;
const REDUCIBLES = new Set(["image/jpeg", "image/png", "image/webp"]);

export async function prepararArchivo(archivo: File): Promise<File> {
  if (!REDUCIBLES.has(archivo.type)) return archivo;
  try {
    const imagen = await createImageBitmap(archivo);
    const escala = Math.min(1, LADO_MAXIMO / Math.max(imagen.width, imagen.height));
    const lienzo = document.createElement("canvas");
    lienzo.width = Math.round(imagen.width * escala);
    lienzo.height = Math.round(imagen.height * escala);
    lienzo.getContext("2d")?.drawImage(imagen, 0, 0, lienzo.width, lienzo.height);
    imagen.close();
    // JPEG para fotos; WebP para PNG y WebP, que pueden traer transparencia.
    const tipo = archivo.type === "image/jpeg" ? "image/jpeg" : "image/webp";
    const blob = await new Promise<Blob | null>((ok) => lienzo.toBlob(ok, tipo, CALIDAD));
    if (!blob || blob.size >= archivo.size) return archivo;
    const extension = tipo === "image/jpeg" ? ".jpg" : ".webp";
    const nombre = archivo.name.replace(/\.[^.]+$/, "") + extension;
    return new File([blob], nombre, { type: tipo });
  } catch {
    return archivo; // formato que el navegador no sabe abrir: va como está
  }
}

export function tamanoLegible(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace(/\.0$/, "")} MB`;
}
