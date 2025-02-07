interface SearchResultProps {
  title: string;
  link: string;
  snippet: string;
}

export const SearchResult = ({ title, link, snippet }: SearchResultProps) => (
  <div className="border-l-4 border-purple-200 pl-4 my-4">
    <h3 className="font-medium">{title}</h3>
    <p className="text-sm text-gray-600 my-1">{snippet}</p>
    <a href={link} target="_blank" rel="noopener noreferrer" 
      className="text-xs text-purple-500 hover:underline">
      {link}
    </a>
  </div>
); 