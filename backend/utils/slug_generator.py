"""
Slug Generator for creating human-readable, URL-safe identifiers.

This module provides a slug-based ID system that's:
- Human-readable
- Error-prone (consistent format)
- Handles duplicates with auto-incrementing
- Preserves Chinese/Unicode characters
"""
import re
from typing import List, Dict


class SlugGenerator:
    """Generates and manages slugs for profiles, characters, and other entities."""
    
    def __init__(self):
        self.slug_cache: Dict[str, str] = {}  # Map from original name to slug
        self.used_slugs: List[str] = []  # Track all used slugs
    
    def generate_slug(self, name: str) -> str:
        """
        Generate a URL-safe slug from a name.
        
        Args:
            name: The original name (e.g., "Alex Smith", "Zhou Yiming (周一鸣)")
            
        Returns:
            A slug like "alex-smith", "zhou-yiming-周一鸣", "alex-2"
        """
        if not name or not name.strip():
            raise ValueError("Name cannot be empty")
        
        # Check cache first
        if name in self.slug_cache:
            return self.slug_cache[name]
        
        # Generate base slug
        base_slug = self._create_base_slug(name)
        
        # Handle duplicates
        final_slug = self._ensure_unique(base_slug)
        
        # Cache and track
        self.slug_cache[name] = final_slug
        self.used_slugs.append(final_slug)
        
        return final_slug
    
    def _create_base_slug(self, name: str) -> str:
        """
        Create the base slug from a name.
        
        Rules:
        1. Convert to lowercase
        2. Replace spaces with hyphens
        3. Remove special characters except hyphens and underscores
        4. Preserve Chinese/Unicode characters
        5. Remove leading/trailing hyphens
        6. Collapse multiple hyphens into one
        """
        # Convert to lowercase
        slug = name.lower()
        
        # Replace spaces and common separators with hyphens
        slug = re.sub(r'[\s_]+', '-', slug)
        
        # Keep letters (including Chinese), numbers, and hyphens
        # \u4e00-\u9fff is the range for Chinese characters
        slug = re.sub(r'[^\w\u4e00-\u9fff-]', '', slug)
        
        # Remove leading/trailing hyphens
        slug = slug.strip('-')
        
        # Collapse multiple consecutive hyphens
        slug = re.sub(r'-+', '-', slug)
        
        # Ensure it's not empty
        if not slug:
            slug = "unnamed"
        
        return slug
    
    def _ensure_unique(self, base_slug: str) -> str:
        """
        Ensure the slug is unique by appending numbers if needed.
        
        Args:
            base_slug: The base slug (e.g., "alex")
            
        Returns:
            A unique slug (e.g., "alex", "alex-2", "alex-3")
        """
        if base_slug not in self.used_slugs:
            return base_slug
        
        # Find the next available number
        counter = 2
        while True:
            candidate = f"{base_slug}-{counter}"
            if candidate not in self.used_slugs:
                return candidate
            counter += 1
    
    def lookup_name(self, slug: str) -> str:
        """
        Look up the original name from a slug.
        
        Args:
            slug: The slug (e.g., "alex-smith")
            
        Returns:
            The original name or None if not found
        """
        # Reverse lookup
        for name, cached_slug in self.slug_cache.items():
            if cached_slug == slug:
                return name
        return None
    
    def clear_cache(self):
        """Clear the slug cache (useful for testing)."""
        self.slug_cache.clear()
        self.used_slugs.clear()


# Global instance for use across the application
_slug_generator = SlugGenerator()


def generate_slug(name: str) -> str:
    """
    Generate a URL-safe slug from a name.
    
    This is the main entry point for generating slugs.
    
    Example:
        >>> generate_slug("Alex Smith")
        'alex-smith'
        >>> generate_slug("Zhou Yiming (周一鸣)")
        'zhou-yiming-周一鸣'
        >>> generate_slug("Alex")  # If "alex" exists
        'alex-2'
    """
    return _slug_generator.generate_slug(name)


def lookup_name(slug: str) -> str:
    """Look up the original name from a slug."""
    return _slug_generator.lookup_name(slug)


def reset_slugs():
    """Reset the slug generator (useful for testing or reloading data)."""
    _slug_generator.clear_cache()


# Example usage and tests
if __name__ == "__main__":
    # Test various name formats
    test_names = [
        "Alex Smith",
        "Zhou Yiming (周一鸣)",
        "Elsa & Anna",
        "MGR - Test 123",
        "Special@Characters!",
        "Multiple   Spaces",
        "Test (Duplicate)",
        "Test (Duplicate)",
        "Test (Duplicate)",
    ]
    
    print("Slug Generation Test:")
    print("=" * 60)
    for name in test_names:
        slug = generate_slug(name)
        print(f"'{name}' → '{slug}'")
    
    print("\n" + "=" * 60)
    print("Duplicate Handling Test:")
    print(f"'Alex Smith' → '{generate_slug('Alex Smith')}'")
    print(f"'Alex Smith' (duplicate) → '{generate_slug('Alex Smith')}'")
    
    # Test lookup
    print("\n" + "=" * 60)
    print("Lookup Test:")
    slug = generate_slug("Test Lookup")
    original = lookup_name(slug)
    print(f"Slug: '{slug}' → Original: '{original}'")

