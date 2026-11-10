// Usage personnel : aucune page n'est proposée aux moteurs de recherche (voir aussi robots: noindex dans layout.jsx).
// L'exploration reste autorisée pour que les moteurs lisent la consigne noindex et retirent les pages déjà indexées.
export default function robots() {
  return { rules: { userAgent: '*', allow: '/' } };
}
