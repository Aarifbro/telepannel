# proxy_manager.py
# Advanced Proxy Management with Health Monitoring and Auto-Rotation

import asyncio
import aiohttp
import time
import random
from typing import List, Dict, Optional, Tuple
from hitter_3d import (load_proxies, save_proxies, parse_proxy_format, 
                       get_proxy_url, get_user_proxies)

class ProxyManager:
    """Advanced proxy management with health monitoring and rotation"""
    
    def __init__(self):
        self.rotation_enabled = {}  # user_id: bool
        self.proxy_health = {}  # proxy_str: {'alive': bool, 'response_time': int, 'last_check': float}
        self.CHECK_INTERVAL = 300  # Check proxies every 5 minutes
        
    def enable_rotation(self, user_id: int, enabled: bool = True):
        """Enable/disable proxy rotation for user"""
        self.rotation_enabled[user_id] = enabled
    
    def is_rotation_enabled(self, user_id: int) -> bool:
        """Check if rotation is enabled for user"""
        return self.rotation_enabled.get(user_id, False)
    
    async def check_proxy_health(self, proxy_str: str, timeout: int = 5) -> Dict:
        """Check if proxy is alive and measure response time"""
        proxy_url = get_proxy_url(proxy_str)
        
        if not proxy_url:
            return {'alive': False, 'response_time': 0, 'error': 'Invalid format'}
        
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    'https://httpbin.org/ip',
                    proxy=proxy_url,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                    ssl=False
                ) as response:
                    response_time = int((time.time() - start_time) * 1000)
                    
                    if response.status == 200:
                        data = await response.json()
                        return {
                            'alive': True,
                            'response_time': response_time,
                            'ip': data.get('origin', 'Unknown'),
                            'error': None
                        }
                    else:
                        return {
                            'alive': False,
                            'response_time': response_time,
                            'error': f'HTTP {response.status}'
                        }
        except asyncio.TimeoutError:
            return {
                'alive': False,
                'response_time': timeout * 1000,
                'error': 'Timeout'
            }
        except Exception as e:
            return {
                'alive': False,
                'response_time': 0,
                'error': str(e)[:50]
            }
    
    async def check_multiple_proxies(self, proxies: List[str], max_concurrent: int = 10) -> List[Dict]:
        """Check multiple proxies concurrently"""
        results = []
        
        for i in range(0, len(proxies), max_concurrent):
            batch = proxies[i:i + max_concurrent]
            tasks = [self.check_proxy_health(proxy) for proxy in batch]
            batch_results = await asyncio.gather(*tasks)
            
            for proxy, result in zip(batch, batch_results):
                results.append({
                    'proxy': proxy,
                    **result
                })
        
        return results
    
    def get_best_proxy(self, user_id: int, prefer_fast: bool = True) -> Optional[str]:
        """
        Get best proxy for user based on health and performance
        
        Args:
            user_id: User ID
            prefer_fast: If True, prefer faster proxies; if False, random selection
        
        Returns:
            Best proxy string or None
        """
        user_proxies = get_user_proxies(user_id)
        
        if not user_proxies:
            return None
        
        # If rotation disabled, return random proxy
        if not self.is_rotation_enabled(user_id):
            return random.choice(user_proxies)
        
        # Filter alive proxies
        alive_proxies = []
        current_time = time.time()
        
        for proxy in user_proxies:
            health = self.proxy_health.get(proxy)
            
            # If no health data or data is old, assume it's alive
            if not health or (current_time - health.get('last_check', 0)) > self.CHECK_INTERVAL:
                alive_proxies.append((proxy, 1000))  # Default 1000ms
            elif health.get('alive'):
                alive_proxies.append((proxy, health.get('response_time', 1000)))
        
        if not alive_proxies:
            # No health data, return random proxy
            return random.choice(user_proxies)
        
        if prefer_fast:
            # Sort by response time and pick fastest
            alive_proxies.sort(key=lambda x: x[1])
            # Pick from top 3 fastest (add randomness)
            top_proxies = alive_proxies[:min(3, len(alive_proxies))]
            return random.choice(top_proxies)[0]
        else:
            # Random from alive proxies
            return random.choice([p[0] for p in alive_proxies])
    
    def update_proxy_health(self, proxy: str, alive: bool, response_time: int):
        """Update proxy health cache"""
        self.proxy_health[proxy] = {
            'alive': alive,
            'response_time': response_time,
            'last_check': time.time()
        }
    
    def get_health_summary(self, user_id: int) -> Dict:
        """Get health summary for user's proxies"""
        user_proxies = get_user_proxies(user_id)
        
        if not user_proxies:
            return {'total': 0, 'alive': 0, 'dead': 0, 'unknown': 0}
        
        alive = 0
        dead = 0
        unknown = 0
        total_response_time = 0
        
        for proxy in user_proxies:
            health = self.proxy_health.get(proxy)
            if not health:
                unknown += 1
            elif health['alive']:
                alive += 1
                total_response_time += health['response_time']
            else:
                dead += 1
        
        avg_response_time = int(total_response_time / alive) if alive > 0 else 0
        
        return {
            'total': len(user_proxies),
            'alive': alive,
            'dead': dead,
            'unknown': unknown,
            'avg_response_time': avg_response_time
        }
    
    async def auto_cleanup_dead_proxies(self, user_id: int, auto_remove: bool = False) -> Tuple[int, List[str]]:
        """
        Check all proxies and optionally remove dead ones
        
        Returns:
            (dead_count, dead_proxies_list)
        """
        user_proxies = get_user_proxies(user_id)
        
        if not user_proxies:
            return 0, []
        
        # Check all proxies
        results = await self.check_multiple_proxies(user_proxies)
        
        dead_proxies = []
        
        for result in results:
            proxy = result['proxy']
            alive = result['alive']
            response_time = result['response_time']
            
            # Update health cache
            self.update_proxy_health(proxy, alive, response_time)
            
            if not alive:
                dead_proxies.append(proxy)
        
        # Auto-remove if enabled
        if auto_remove and dead_proxies:
            proxies_data = load_proxies()
            user_key = str(user_id)
            
            if user_key in proxies_data:
                if isinstance(proxies_data[user_key], list):
                    proxies_data[user_key] = [p for p in proxies_data[user_key] if p not in dead_proxies]
                    if not proxies_data[user_key]:
                        del proxies_data[user_key]
                elif proxies_data[user_key] in dead_proxies:
                    del proxies_data[user_key]
                
                save_proxies(proxies_data)
        
        return len(dead_proxies), dead_proxies
    
    def get_proxy_stats(self, proxy: str) -> Optional[Dict]:
        """Get statistics for a specific proxy"""
        return self.proxy_health.get(proxy)


# Global instance
proxy_manager = ProxyManager()


def get_smart_proxy(user_id: int) -> Optional[str]:
    """Get best proxy with smart selection"""
    return proxy_manager.get_best_proxy(user_id, prefer_fast=True)


def enable_proxy_rotation(user_id: int, enabled: bool = True):
    """Enable/disable smart proxy rotation"""
    proxy_manager.enable_rotation(user_id, enabled)


def is_rotation_enabled(user_id: int) -> bool:
    """Check if smart rotation is enabled"""
    return proxy_manager.is_rotation_enabled(user_id)
