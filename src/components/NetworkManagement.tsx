import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Network,
  Globe,
  Radio,
  ArrowDownUp,
  RefreshCw,
  Search,
  CheckCircle2,
  AlertCircle,
  SlidersHorizontal,
  Route,
  Server,
  Layers,
  ArrowDownLeft,
  ArrowUpRight,
  Shield,
  X,
  ExternalLink,
} from 'lucide-react';
import { apiClient } from '../api/client';
import {
  DNSConfigInfo,
  InterfaceDetailInfo,
  NetworkOverview,
  RouteInfo,
} from '../types/network';

export const NetworkManagement: React.FC = () => {
  const [overview, setOverview] = useState<NetworkOverview | null>(null);
  const [interfaces, setInterfaces] = useState<InterfaceDetailInfo[]>([]);
  const [routes, setRoutes] = useState<RouteInfo[]>([]);
  const [dns, setDns] = useState<DNSConfigInfo | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // View & Filter States
  const [activeSubTab, setActiveSubTab] = useState<'interfaces' | 'routes' | 'dns'>('interfaces');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [typeFilter, setTypeFilter] = useState<'all' | 'physical' | 'virtual' | 'loopback'>('all');
  const [stateFilter, setStateFilter] = useState<'all' | 'up' | 'down'>('all');
  const [autoRefreshInterval, setAutoRefreshInterval] = useState<number>(10);
  const [selectedInterface, setSelectedInterface] = useState<InterfaceDetailInfo | null>(null);

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatPackets = (pkts: number): string => {
    if (pkts >= 1_000_000) return (pkts / 1_000_000).toFixed(1) + 'M';
    if (pkts >= 1_000) return (pkts / 1_000).toFixed(1) + 'K';
    return pkts.toString();
  };

  const fetchData = useCallback(async (showLoading: boolean = false) => {
    if (showLoading) setIsLoading(true);
    setIsRefreshing(true);
    setError(null);

    try {
      const [overviewData, ifacesData, routesData, dnsData] = await Promise.all([
        apiClient.getNetworkOverview(),
        apiClient.getNetworkInterfaces(),
        apiClient.getNetworkRoutes(),
        apiClient.getNetworkDNS(),
      ]);

      setOverview(overviewData);
      setInterfaces(ifacesData);
      setRoutes(routesData);
      setDns(dnsData);

      // If an interface was selected, update its reference
      if (selectedInterface) {
        const updated = ifacesData.find((i) => i.name === selectedInterface.name);
        if (updated) setSelectedInterface(updated);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch network telemetry');
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [selectedInterface]);

  useEffect(() => {
    fetchData(true);
  }, [fetchData]);

  // Controlled auto-refresh with strict cleanup
  useEffect(() => {
    if (autoRefreshInterval <= 0) return;
    const interval = setInterval(() => {
      fetchData(false);
    }, autoRefreshInterval * 1000);

    return () => clearInterval(interval);
  }, [autoRefreshInterval, fetchData]);

  // Filtered Interfaces
  const filteredInterfaces = useMemo(() => {
    return interfaces.filter((iface) => {
      // Type filter
      if (typeFilter === 'physical' && !iface.is_physical) return false;
      if (typeFilter === 'virtual' && !iface.is_virtual) return false;
      if (typeFilter === 'loopback' && !iface.is_loopback) return false;

      // State filter
      const isUp = iface.operational_state === 'up' || iface.administrative_state === 'up';
      if (stateFilter === 'up' && !isUp) return false;
      if (stateFilter === 'down' && isUp) return false;

      // Search query
      if (!searchQuery.trim()) return true;
      const query = searchQuery.toLowerCase();
      const matchName = iface.name.toLowerCase().includes(query);
      const matchMac = iface.mac_address?.toLowerCase().includes(query) || false;
      const matchIp = iface.ipv4_addresses.some((ip) => ip.includes(query)) ||
                      iface.ipv6_addresses.some((ip) => ip.toLowerCase().includes(query));
      const matchType = iface.iftype.toLowerCase().includes(query);

      return matchName || matchMac || matchIp || matchType;
    });
  }, [interfaces, typeFilter, stateFilter, searchQuery]);

  // Filtered Routes
  const filteredRoutes = useMemo(() => {
    if (!searchQuery.trim()) return routes;
    const query = searchQuery.toLowerCase();
    return routes.filter(
      (r) =>
        r.destination.toLowerCase().includes(query) ||
        r.gateway.toLowerCase().includes(query) ||
        r.interface.toLowerCase().includes(query) ||
        r.family.toLowerCase().includes(query)
    );
  }, [routes, searchQuery]);

  return (
    <div id="network-management-view" className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-neutral-800">
        <div>
          <h2 className="text-lg font-medium text-white flex items-center gap-2">
            <Radio className="w-5 h-5 text-neutral-400" />
            Network Management Foundation
          </h2>
          <p className="text-xs text-neutral-400 mt-0.5">
            Read-only network interfaces, IP addresses, routing tables, and DNS configuration
          </p>
        </div>

        <div className="flex items-center gap-2.5 self-start sm:self-auto">
          {/* Refresh Interval Selector */}
          <div className="flex items-center space-x-1 bg-neutral-900 border border-neutral-800 rounded-lg p-1 text-xs text-neutral-400">
            <SlidersHorizontal className="w-3.5 h-3.5 ml-1 mr-0.5 text-neutral-500" />
            <span className="text-[11px] mr-1 hidden md:inline">Refresh:</span>
            {[
              { label: 'Off', val: 0 },
              { label: '5s', val: 5 },
              { label: '10s', val: 10 },
              { label: '30s', val: 30 },
            ].map((item) => (
              <button
                key={item.val}
                id={`network-refresh-${item.val}s-btn`}
                onClick={() => setAutoRefreshInterval(item.val)}
                className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
                  autoRefreshInterval === item.val
                    ? 'bg-neutral-800 text-white shadow-xs'
                    : 'text-neutral-400 hover:text-white'
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>

          {/* Manual Refresh Button */}
          <button
            id="network-manual-refresh-btn"
            onClick={() => fetchData(false)}
            disabled={isRefreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-750 text-xs font-medium text-neutral-200 border border-neutral-700/60 transition-colors disabled:opacity-50 shadow-xs"
            title="Refresh network telemetry"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-emerald-400' : 'text-neutral-400'}`} />
            <span className="hidden sm:inline">Refresh</span>
          </button>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div id="network-error-alert" className="p-3.5 bg-rose-950/40 border border-rose-800/60 rounded-xl flex items-start space-x-3 text-rose-300 text-xs">
          <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0 text-rose-400" />
          <div className="flex-1">
            <span className="font-semibold text-rose-200">Network Telemetry Error:</span> {error}
          </div>
          <button
            onClick={() => fetchData(true)}
            className="px-2 py-1 bg-rose-900/60 hover:bg-rose-900 rounded text-rose-200 text-[11px] font-medium transition-colors"
          >
            Retry
          </button>
        </div>
      )}

      {/* Network Overview KPI Summary Cards */}
      {overview && (
        <div id="network-overview-kpi-grid" className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
          {/* Total Interfaces */}
          <div className="bg-neutral-900/90 border border-neutral-800/80 rounded-xl p-4 shadow-xs">
            <div className="flex items-center justify-between text-neutral-400 text-xs mb-1.5">
              <span className="font-medium text-neutral-300">Interfaces</span>
              <Network className="w-4 h-4 text-neutral-400" />
            </div>
            <div className="text-xl font-semibold text-white tracking-tight">
              {overview.total_interfaces}
              <span className="text-xs font-normal text-neutral-400 ml-2">
                ({overview.up_interfaces} up, {overview.down_interfaces} down)
              </span>
            </div>
            <div className="mt-2 text-[11px] text-neutral-400 flex items-center gap-2">
              <span className="inline-flex items-center gap-1 text-emerald-400">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                {overview.physical_interfaces} physical
              </span>
              <span className="text-neutral-600">•</span>
              <span>{overview.virtual_interfaces} virtual</span>
              <span className="text-neutral-600">•</span>
              <span>{overview.loopback_interfaces} loopback</span>
            </div>
          </div>

          {/* IPv4 & IPv6 Addresses */}
          <div className="bg-neutral-900/90 border border-neutral-800/80 rounded-xl p-4 shadow-xs">
            <div className="flex items-center justify-between text-neutral-400 text-xs mb-1.5">
              <span className="font-medium text-neutral-300">IP Addresses</span>
              <Globe className="w-4 h-4 text-neutral-400" />
            </div>
            <div className="text-xl font-semibold text-white tracking-tight">
              {overview.ipv4_addresses.length}
              <span className="text-xs font-normal text-neutral-400 ml-1.5">IPv4</span>
              <span className="text-neutral-600 mx-1.5">•</span>
              {overview.ipv6_addresses.length}
              <span className="text-xs font-normal text-neutral-400 ml-1.5">IPv6</span>
            </div>
            <div className="mt-2 text-[11px] text-neutral-400 truncate font-mono">
              {overview.ipv4_addresses.find((ip) => !ip.startsWith('127.')) || overview.ipv4_addresses[0] || 'No IPv4 assigned'}
            </div>
          </div>

          {/* Default Gateway Route */}
          <div className="bg-neutral-900/90 border border-neutral-800/80 rounded-xl p-4 shadow-xs">
            <div className="flex items-center justify-between text-neutral-400 text-xs mb-1.5">
              <span className="font-medium text-neutral-300">Default Gateway</span>
              <Route className="w-4 h-4 text-neutral-400" />
            </div>
            <div className="text-base font-medium text-white tracking-tight font-mono truncate">
              {overview.default_ipv4_route || overview.default_ipv6_route || 'None'}
            </div>
            <div className="mt-2 text-[11px] text-neutral-400 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-500"></span>
              <span>Default IPv4 routing target</span>
            </div>
          </div>

          {/* Primary DNS Nameservers */}
          <div className="bg-neutral-900/90 border border-neutral-800/80 rounded-xl p-4 shadow-xs">
            <div className="flex items-center justify-between text-neutral-400 text-xs mb-1.5">
              <span className="font-medium text-neutral-300">DNS Resolver</span>
              <Server className="w-4 h-4 text-neutral-400" />
            </div>
            <div className="text-base font-medium text-white tracking-tight font-mono truncate">
              {overview.dns_servers.length > 0 ? overview.dns_servers[0] : 'None configured'}
            </div>
            <div className="mt-2 text-[11px] text-neutral-400 flex items-center gap-1.5">
              <span className="text-neutral-300">{overview.dns_servers.length} nameservers</span>
              {dns && <span className="text-neutral-500 font-mono">({dns.source})</span>}
            </div>
          </div>
        </div>
      )}

      {/* Sub-Tab Navigation & Search Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pt-2">
        <div className="flex items-center space-x-1 bg-neutral-900 p-1 rounded-xl border border-neutral-800 w-fit">
          <button
            id="subtab-interfaces-btn"
            onClick={() => setActiveSubTab('interfaces')}
            className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              activeSubTab === 'interfaces'
                ? 'bg-neutral-800 text-white shadow-xs'
                : 'text-neutral-400 hover:text-white'
            }`}
          >
            <Radio className="w-3.5 h-3.5 text-neutral-400" />
            <span>Interfaces ({interfaces.length})</span>
          </button>

          <button
            id="subtab-routes-btn"
            onClick={() => setActiveSubTab('routes')}
            className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              activeSubTab === 'routes'
                ? 'bg-neutral-800 text-white shadow-xs'
                : 'text-neutral-400 hover:text-white'
            }`}
          >
            <Route className="w-3.5 h-3.5 text-neutral-400" />
            <span>Routing Table ({routes.length})</span>
          </button>

          <button
            id="subtab-dns-btn"
            onClick={() => setActiveSubTab('dns')}
            className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              activeSubTab === 'dns'
                ? 'bg-neutral-800 text-white shadow-xs'
                : 'text-neutral-400 hover:text-white'
            }`}
          >
            <Server className="w-3.5 h-3.5 text-neutral-400" />
            <span>DNS Configuration</span>
          </button>
        </div>

        {/* Search & Filters */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Search Box */}
          <div className="relative flex-1 md:w-64">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-neutral-500" />
            <input
              id="network-search-input"
              type="text"
              placeholder={
                activeSubTab === 'interfaces'
                  ? 'Filter by interface, MAC, IP...'
                  : activeSubTab === 'routes'
                  ? 'Filter destination, gateway...'
                  : 'Search...'
              }
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-neutral-900 border border-neutral-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-neutral-200 placeholder-neutral-500 focus:outline-hidden focus:border-neutral-700"
            />
          </div>

          {/* Interface specific type & state filters */}
          {activeSubTab === 'interfaces' && (
            <div className="flex items-center gap-1.5">
              <select
                id="network-type-filter-select"
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value as any)}
                className="bg-neutral-900 border border-neutral-800 rounded-lg px-2.5 py-1.5 text-xs text-neutral-300 focus:outline-hidden focus:border-neutral-700"
              >
                <option value="all">All Types</option>
                <option value="physical">Physical</option>
                <option value="virtual">Virtual</option>
                <option value="loopback">Loopback</option>
              </select>

              <select
                id="network-state-filter-select"
                value={stateFilter}
                onChange={(e) => setStateFilter(e.target.value as any)}
                className="bg-neutral-900 border border-neutral-800 rounded-lg px-2.5 py-1.5 text-xs text-neutral-300 focus:outline-hidden focus:border-neutral-700"
              >
                <option value="all">All States</option>
                <option value="up">State: Up</option>
                <option value="down">State: Down</option>
              </select>
            </div>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      {isLoading && interfaces.length === 0 ? (
        <div className="space-y-3 py-6">
          <div className="h-16 bg-neutral-900 animate-pulse rounded-xl"></div>
          <div className="h-16 bg-neutral-900 animate-pulse rounded-xl"></div>
          <div className="h-16 bg-neutral-900 animate-pulse rounded-xl"></div>
        </div>
      ) : activeSubTab === 'interfaces' ? (
        /* INTERFACES VIEW */
        <div className="space-y-4">
          <div className="bg-neutral-900/90 border border-neutral-800/80 rounded-xl overflow-hidden shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-neutral-800 bg-neutral-950/60 text-neutral-400 font-medium">
                    <th className="py-3 px-4">Interface</th>
                    <th className="py-3 px-3">State</th>
                    <th className="py-3 px-3">Type</th>
                    <th className="py-3 px-3">MAC / MTU</th>
                    <th className="py-3 px-3">IP Addresses</th>
                    <th className="py-3 px-3">Traffic (RX / TX)</th>
                    <th className="py-3 px-4 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-800/60 font-normal">
                  {filteredInterfaces.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-neutral-400">
                        No network interfaces matching the filter criteria.
                      </td>
                    </tr>
                  ) : (
                    filteredInterfaces.map((iface) => {
                      const isUp = iface.operational_state === 'up' || iface.administrative_state === 'up';

                      return (
                        <tr
                          key={iface.name}
                          id={`iface-row-${iface.name}`}
                          className="hover:bg-neutral-850/40 transition-colors"
                        >
                          {/* Name & Index */}
                          <td className="py-3.5 px-4">
                            <div className="flex items-center space-x-2.5">
                              <Radio className="w-4 h-4 text-neutral-400 shrink-0" />
                              <div>
                                <div className="font-medium text-white font-mono text-xs flex items-center gap-1.5">
                                  {iface.name}
                                  {iface.index !== null && iface.index !== undefined && (
                                    <span className="text-[10px] text-neutral-400 font-normal">#{iface.index}</span>
                                  )}
                                </div>
                                <div className="text-[11px] text-neutral-400 capitalize">
                                  {iface.iftype}
                                  {iface.speed_mbps ? ` • ${iface.speed_mbps} Mbps` : ''}
                                </div>
                              </div>
                            </div>
                          </td>

                          {/* Operstate Badge */}
                          <td className="py-3.5 px-3">
                            <span
                              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium ${
                                isUp
                                  ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-800/50'
                                  : 'bg-neutral-800 text-neutral-400 border border-neutral-700/50'
                              }`}
                            >
                              <span
                                className={`w-1.5 h-1.5 rounded-full ${
                                  isUp ? 'bg-emerald-400' : 'bg-neutral-500'
                                }`}
                              ></span>
                              {iface.operational_state.toUpperCase()}
                            </span>
                          </td>

                          {/* Classification Badge */}
                          <td className="py-3.5 px-3">
                            <span
                              className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono ${
                                iface.is_physical
                                  ? 'bg-blue-950/60 text-blue-300 border border-blue-800/50'
                                  : iface.is_virtual
                                  ? 'bg-purple-950/60 text-purple-300 border border-purple-800/50'
                                  : 'bg-neutral-800 text-neutral-400'
                              }`}
                            >
                              {iface.is_physical
                                ? 'physical'
                                : iface.is_virtual
                                ? 'virtual'
                                : 'loopback'}
                            </span>
                          </td>

                          {/* MAC & MTU */}
                          <td className="py-3.5 px-3">
                            <div className="font-mono text-[11px] text-neutral-300">
                              {iface.mac_address || '—'}
                            </div>
                            <div className="text-[10px] text-neutral-400">MTU {iface.mtu || 1500}</div>
                          </td>

                          {/* IP Addresses */}
                          <td className="py-3.5 px-3">
                            <div className="space-y-0.5 max-w-xs">
                              {iface.ipv4_addresses.length > 0 && (
                                <div className="font-mono text-xs text-neutral-200 truncate">
                                  {iface.ipv4_addresses.join(', ')}
                                </div>
                              )}
                              {iface.ipv6_addresses.length > 0 && (
                                <div className="font-mono text-[10px] text-neutral-400 truncate" title={iface.ipv6_addresses.join(', ')}>
                                  {iface.ipv6_addresses[0]}
                                  {iface.ipv6_addresses.length > 1 ? ` (+${iface.ipv6_addresses.length - 1})` : ''}
                                </div>
                              )}
                              {iface.ipv4_addresses.length === 0 && iface.ipv6_addresses.length === 0 && (
                                <span className="text-neutral-500 italic text-[11px]">No IP assigned</span>
                              )}
                            </div>
                          </td>

                          {/* Traffic RX / TX */}
                          <td className="py-3.5 px-3">
                            <div className="space-y-1">
                              <div className="flex items-center gap-1 text-[11px] text-neutral-300">
                                <ArrowDownLeft className="w-3 h-3 text-emerald-400 shrink-0" />
                                <span className="font-mono">{formatBytes(iface.stats.rx_bytes)}</span>
                                <span className="text-[10px] text-neutral-500">
                                  ({formatPackets(iface.stats.rx_packets)} pkts)
                                </span>
                              </div>
                              <div className="flex items-center gap-1 text-[11px] text-neutral-300">
                                <ArrowUpRight className="w-3 h-3 text-blue-400 shrink-0" />
                                <span className="font-mono">{formatBytes(iface.stats.tx_bytes)}</span>
                                <span className="text-[10px] text-neutral-500">
                                  ({formatPackets(iface.stats.tx_packets)} pkts)
                                </span>
                              </div>
                              {(iface.stats.rx_errors > 0 || iface.stats.tx_errors > 0) && (
                                <div className="text-[10px] text-rose-400 font-medium">
                                  Errors: RX {iface.stats.rx_errors}, TX {iface.stats.tx_errors}
                                </div>
                              )}
                            </div>
                          </td>

                          {/* Action Button */}
                          <td className="py-3.5 px-4 text-right">
                            <button
                              id={`iface-detail-btn-${iface.name}`}
                              onClick={() => setSelectedInterface(iface)}
                              className="px-2.5 py-1 rounded bg-neutral-800 hover:bg-neutral-750 text-neutral-200 text-[11px] font-medium border border-neutral-700/60 transition-colors shadow-xs"
                            >
                              Details
                            </button>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : activeSubTab === 'routes' ? (
        /* ROUTING TABLE VIEW */
        <div className="space-y-4">
          <div className="bg-neutral-900/90 border border-neutral-800/80 rounded-xl overflow-hidden shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-neutral-800 bg-neutral-950/60 text-neutral-400 font-medium">
                    <th className="py-3 px-4">Destination / Mask</th>
                    <th className="py-3 px-3">Gateway</th>
                    <th className="py-3 px-3">Interface</th>
                    <th className="py-3 px-3">Family</th>
                    <th className="py-3 px-3">Flags</th>
                    <th className="py-3 px-4 text-right">Metric</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-800/60 font-normal">
                  {filteredRoutes.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-neutral-400">
                        No routing table entries discovered.
                      </td>
                    </tr>
                  ) : (
                    filteredRoutes.map((route, idx) => (
                      <tr
                        key={`${route.interface}-${route.destination}-${idx}`}
                        className={`hover:bg-neutral-850/40 transition-colors ${
                          route.is_default ? 'bg-blue-950/10' : ''
                        }`}
                      >
                        {/* Destination */}
                        <td className="py-3 px-4 font-mono font-medium text-white flex items-center gap-2">
                          <span>{route.destination}</span>
                          {route.is_default && (
                            <span className="px-1.5 py-0.5 rounded bg-blue-900/60 text-blue-300 text-[10px] font-sans font-medium">
                              Default
                            </span>
                          )}
                        </td>

                        {/* Gateway */}
                        <td className="py-3 px-3 font-mono text-neutral-300">
                          {route.gateway !== '0.0.0.0' && route.gateway.trim() !== '0'
                            ? route.gateway
                            : '—'}
                        </td>

                        {/* Interface */}
                        <td className="py-3 px-3 font-mono text-neutral-200">
                          <span className="px-2 py-0.5 rounded bg-neutral-800 text-neutral-300">
                            {route.interface}
                          </span>
                        </td>

                        {/* Family */}
                        <td className="py-3 px-3 uppercase text-[11px] text-neutral-400">
                          {route.family}
                        </td>

                        {/* Flags */}
                        <td className="py-3 px-3 font-mono text-[11px] text-neutral-400">
                          {route.flags}
                        </td>

                        {/* Metric */}
                        <td className="py-3 px-4 text-right font-mono text-neutral-300">
                          {route.metric}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : (
        /* DNS CONFIGURATION VIEW */
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Nameservers Card */}
            <div className="bg-neutral-900/90 border border-neutral-800/80 rounded-xl p-5 shadow-xs">
              <div className="flex items-center justify-between mb-3 text-neutral-300">
                <h3 className="font-medium text-white text-sm flex items-center gap-2">
                  <Server className="w-4 h-4 text-neutral-400" />
                  Nameservers
                </h3>
                <span className="text-[11px] px-2 py-0.5 rounded bg-neutral-800 text-neutral-400">
                  {dns?.nameservers.length || 0} active
                </span>
              </div>
              <div className="space-y-2 font-mono text-xs">
                {dns && dns.nameservers.length > 0 ? (
                  dns.nameservers.map((ns, idx) => (
                    <div
                      key={ns}
                      className="p-2.5 rounded-lg bg-neutral-950/70 border border-neutral-800 flex items-center justify-between text-neutral-200"
                    >
                      <span>{ns}</span>
                      <span className="text-[10px] text-neutral-500 font-sans">
                        {idx === 0 ? 'Primary' : `Secondary #${idx}`}
                      </span>
                    </div>
                  ))
                ) : (
                  <div className="text-neutral-500 italic py-3 text-center">
                    No nameservers found in /etc/resolv.conf
                  </div>
                )}
              </div>
            </div>

            {/* Search Domains Card */}
            <div className="bg-neutral-900/90 border border-neutral-800/80 rounded-xl p-5 shadow-xs">
              <div className="flex items-center justify-between mb-3 text-neutral-300">
                <h3 className="font-medium text-white text-sm flex items-center gap-2">
                  <Globe className="w-4 h-4 text-neutral-400" />
                  Search Domains
                </h3>
                <span className="text-[11px] px-2 py-0.5 rounded bg-neutral-800 text-neutral-400">
                  {dns?.search_domains.length || 0} domains
                </span>
              </div>
              <div className="space-y-2 font-mono text-xs">
                {dns && dns.search_domains.length > 0 ? (
                  dns.search_domains.map((dom) => (
                    <div
                      key={dom}
                      className="p-2.5 rounded-lg bg-neutral-950/70 border border-neutral-800 text-neutral-200"
                    >
                      {dom}
                    </div>
                  ))
                ) : (
                  <div className="text-neutral-500 italic py-3 text-center">
                    No search domains configured
                  </div>
                )}
              </div>
            </div>

            {/* Resolver Meta & Options Card */}
            <div className="bg-neutral-900/90 border border-neutral-800/80 rounded-xl p-5 shadow-xs">
              <div className="flex items-center justify-between mb-3 text-neutral-300">
                <h3 className="font-medium text-white text-sm flex items-center gap-2">
                  <Shield className="w-4 h-4 text-neutral-400" />
                  Resolver Metadata
                </h3>
              </div>
              <div className="space-y-3 text-xs">
                <div>
                  <div className="text-neutral-400 text-[11px]">Configuration Source</div>
                  <div className="font-medium text-white mt-0.5 flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                    <span>{dns?.source || 'static'}</span>
                  </div>
                </div>

                <div>
                  <div className="text-neutral-400 text-[11px]">Symlink Target</div>
                  <div className="font-mono text-[11px] text-neutral-300 mt-0.5 break-all">
                    {dns?.symlink_target || '/etc/resolv.conf (Direct file)'}
                  </div>
                </div>

                {dns?.options && dns.options.length > 0 && (
                  <div>
                    <div className="text-neutral-400 text-[11px]">Configured Options</div>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {dns.options.map((opt) => (
                        <span key={opt} className="px-2 py-0.5 rounded bg-neutral-800 font-mono text-[11px] text-neutral-300">
                          {opt}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Interface Detail Modal / Drawer */}
      {selectedInterface && (
        <div
          id="interface-detail-modal-backdrop"
          className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4"
          onClick={() => setSelectedInterface(null)}
        >
          <div
            id="interface-detail-modal"
            className="bg-neutral-900 border border-neutral-800 rounded-2xl w-full max-w-2xl max-h-[85vh] overflow-y-auto shadow-2xl p-6 space-y-5"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-start justify-between pb-3 border-b border-neutral-800">
              <div className="flex items-center space-x-3">
                <div className="p-2 rounded-xl bg-neutral-800 text-neutral-300">
                  <Radio className="w-5 h-5 text-neutral-400" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-base font-semibold text-white font-mono">{selectedInterface.name}</h3>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-medium uppercase ${
                        selectedInterface.operational_state === 'up'
                          ? 'bg-emerald-950 text-emerald-400 border border-emerald-800/50'
                          : 'bg-neutral-800 text-neutral-400'
                      }`}
                    >
                      {selectedInterface.operational_state}
                    </span>
                  </div>
                  <p className="text-xs text-neutral-400 mt-0.5">
                    {selectedInterface.iftype} • {selectedInterface.is_physical ? 'Physical Adapter' : selectedInterface.is_virtual ? 'Virtual Device' : 'Loopback'}
                  </p>
                </div>
              </div>

              <button
                id="close-iface-detail-btn"
                onClick={() => setSelectedInterface(null)}
                className="p-1 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Hardware & Identity Specs */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div className="p-3 bg-neutral-950/60 rounded-xl border border-neutral-800/80">
                <div className="text-neutral-500 text-[10px] uppercase font-mono">MAC Address</div>
                <div className="font-mono text-neutral-200 mt-1 truncate">{selectedInterface.mac_address || '—'}</div>
              </div>
              <div className="p-3 bg-neutral-950/60 rounded-xl border border-neutral-800/80">
                <div className="text-neutral-500 text-[10px] uppercase font-mono">MTU</div>
                <div className="font-mono text-neutral-200 mt-1">{selectedInterface.mtu || 1500} bytes</div>
              </div>
              <div className="p-3 bg-neutral-950/60 rounded-xl border border-neutral-800/80">
                <div className="text-neutral-500 text-[10px] uppercase font-mono">Link Speed</div>
                <div className="font-mono text-neutral-200 mt-1">
                  {selectedInterface.speed_mbps ? `${selectedInterface.speed_mbps} Mbps` : 'Virtual / N/A'}
                </div>
              </div>
              <div className="p-3 bg-neutral-950/60 rounded-xl border border-neutral-800/80">
                <div className="text-neutral-500 text-[10px] uppercase font-mono">Duplex Mode</div>
                <div className="font-mono text-neutral-200 mt-1 capitalize">{selectedInterface.duplex || 'N/A'}</div>
              </div>
            </div>

            {/* Flags */}
            <div>
              <h4 className="text-xs font-medium text-neutral-300 mb-2">Interface Flags</h4>
              <div className="flex flex-wrap gap-1.5">
                {selectedInterface.flags.map((flag) => (
                  <span
                    key={flag}
                    className="px-2 py-0.5 rounded bg-neutral-800 border border-neutral-700/60 text-neutral-300 font-mono text-[11px]"
                  >
                    {flag}
                  </span>
                ))}
              </div>
            </div>

            {/* Configured IP Addresses */}
            <div>
              <h4 className="text-xs font-medium text-neutral-300 mb-2">Configured IP Addresses</h4>
              <div className="space-y-1.5">
                {selectedInterface.addresses.length === 0 ? (
                  <div className="p-3 bg-neutral-950/60 rounded-xl border border-neutral-800 text-neutral-500 text-xs text-center">
                    No IPv4 or IPv6 addresses configured on this interface.
                  </div>
                ) : (
                  selectedInterface.addresses.map((addr, i) => (
                    <div
                      key={i}
                      className="p-3 bg-neutral-950/60 rounded-xl border border-neutral-800 flex items-center justify-between text-xs"
                    >
                      <div className="flex items-center space-x-2">
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-medium uppercase ${
                            addr.family === 'ipv4'
                              ? 'bg-blue-950 text-blue-300'
                              : 'bg-purple-950 text-purple-300'
                          }`}
                        >
                          {addr.family}
                        </span>
                        <span className="font-mono text-white">
                          {addr.address}
                          {addr.prefix_length !== null && addr.prefix_length !== undefined ? `/${addr.prefix_length}` : ''}
                        </span>
                      </div>
                      <span className="text-[11px] text-neutral-400 capitalize">Scope: {addr.scope || 'global'}</span>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Traffic Statistics Detail */}
            <div>
              <h4 className="text-xs font-medium text-neutral-300 mb-2">Traffic &amp; Error Telemetry</h4>
              <div className="grid grid-cols-2 gap-3 text-xs">
                {/* RX Stats */}
                <div className="p-3.5 bg-neutral-950/70 rounded-xl border border-neutral-800/80 space-y-1.5">
                  <div className="flex items-center gap-1.5 text-emerald-400 font-medium text-xs mb-2">
                    <ArrowDownLeft className="w-4 h-4" />
                    <span>Inbound (RX)</span>
                  </div>
                  <div className="flex justify-between text-neutral-300">
                    <span className="text-neutral-500">Bytes:</span>
                    <span className="font-mono">{formatBytes(selectedInterface.stats.rx_bytes)}</span>
                  </div>
                  <div className="flex justify-between text-neutral-300">
                    <span className="text-neutral-500">Packets:</span>
                    <span className="font-mono">{selectedInterface.stats.rx_packets.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between text-neutral-300">
                    <span className="text-neutral-500">Errors:</span>
                    <span className={`font-mono ${selectedInterface.stats.rx_errors > 0 ? 'text-rose-400 font-bold' : ''}`}>
                      {selectedInterface.stats.rx_errors}
                    </span>
                  </div>
                  <div className="flex justify-between text-neutral-300">
                    <span className="text-neutral-500">Dropped:</span>
                    <span className="font-mono">{selectedInterface.stats.rx_dropped}</span>
                  </div>
                </div>

                {/* TX Stats */}
                <div className="p-3.5 bg-neutral-950/70 rounded-xl border border-neutral-800/80 space-y-1.5">
                  <div className="flex items-center gap-1.5 text-blue-400 font-medium text-xs mb-2">
                    <ArrowUpRight className="w-4 h-4" />
                    <span>Outbound (TX)</span>
                  </div>
                  <div className="flex justify-between text-neutral-300">
                    <span className="text-neutral-500">Bytes:</span>
                    <span className="font-mono">{formatBytes(selectedInterface.stats.tx_bytes)}</span>
                  </div>
                  <div className="flex justify-between text-neutral-300">
                    <span className="text-neutral-500">Packets:</span>
                    <span className="font-mono">{selectedInterface.stats.tx_packets.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between text-neutral-300">
                    <span className="text-neutral-500">Errors:</span>
                    <span className={`font-mono ${selectedInterface.stats.tx_errors > 0 ? 'text-rose-400 font-bold' : ''}`}>
                      {selectedInterface.stats.tx_errors}
                    </span>
                  </div>
                  <div className="flex justify-between text-neutral-300">
                    <span className="text-neutral-500">Dropped:</span>
                    <span className="font-mono">{selectedInterface.stats.tx_dropped}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
