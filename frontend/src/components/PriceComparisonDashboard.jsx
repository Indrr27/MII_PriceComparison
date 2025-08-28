// PriceComparisonDashboard.jsx
import React, { useState, useEffect } from 'react';
import { 
  ShoppingCart, TrendingDown, TrendingUp, DollarSign, Package, 
  Store, Award, AlertCircle, Download, RefreshCw, Search,
  ChevronUp, ChevronDown, Filter
} from 'lucide-react';


const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const PriceComparisonDashboard = () => {
  const [stores, setStores] = useState([]);
  const [selectedStoreId, setSelectedStoreId] = useState(null);
  const [comparisonData, setComparisonData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(0);
  const [productsPerPage] = useState(50);
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortField, setSortField] = useState('savings_percent');
  const [sortDirection, setSortDirection] = useState('desc');
  const [displayedProducts, setDisplayedProducts] = useState([]);

  // update tab title
  useEffect(() => {
    document.title = 'Demo - Price Comparison';
  }, []);

  // get stores when component loads
  useEffect(() => {
    fetchStores();
  }, []);

  // get comparison data when store or filters change
  useEffect(() => {
    if (selectedStoreId) {
      fetchComparisonData(selectedStoreId);
    }
  }, [selectedStoreId, selectedCategory, searchQuery]);

  // sort products when sort settings change
  useEffect(() => {
    if (comparisonData?.products) {
      sortProducts(comparisonData.products);
    }
  }, [sortField, sortDirection, comparisonData]);

  const fetchStores = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/api/price-comparison/stores`);
      if (!response.ok) throw new Error('Failed to fetch stores');
      const data = await response.json();
      
      setStores(data);
      // pick first competitor by default
      const firstCompetitor = data.find(s => !s.is_primary);
      if (firstCompetitor) {
        setSelectedStoreId(firstCompetitor.id);
      }
    } catch (err) {
      setError(err.message);
      console.error('Error fetching stores:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchComparisonData = async (storeId) => {
    try {
      setLoading(true);
      setError(null);
      
      // build url with filters
      let url = `${API_BASE_URL}/api/price-comparison/comparison/${storeId}?limit=1000`;
      if (selectedCategory && selectedCategory !== 'All') {
        url += `&category=${encodeURIComponent(selectedCategory)}`;
      }
      if (searchQuery) {
        url += `&search=${encodeURIComponent(searchQuery)}`;
      }
      
      const response = await fetch(url);
      if (!response.ok) throw new Error('Failed to fetch comparison data');
      const data = await response.json();
      setComparisonData(data);
    } catch (err) {
      setError(err.message);
      console.error('Error fetching comparison:', err);
    } finally {
      setLoading(false);
    }
  };

  const sortProducts = (products) => {
    const sorted = [...products].sort((a, b) => {
      let aVal, bVal;
      
      switch(sortField) {
        case 'size':
          // extract numeric value from size
          aVal = parseFloat(a.primary_product_size?.match(/[\d.]+/)?.[0] || 0);
          bVal = parseFloat(b.primary_product_size?.match(/[\d.]+/)?.[0] || 0);
          break;
        case 'our_price':
          aVal = a.our_price;
          bVal = b.our_price;
          break;
        case 'their_price':
          aVal = a.their_price;
          bVal = b.their_price;
          break;
        case 'savings':
          aVal = Math.abs(a.savings);
          bVal = Math.abs(b.savings);
          break;
        case 'savings_percent':
          aVal = a.savings_percent;
          bVal = b.savings_percent;
          break;
        case 'match':
          aVal = a.match_confidence;
          bVal = b.match_confidence;
          break;
        default:
          aVal = a.primary_product_name;
          bVal = b.primary_product_name;
      }
      
      if (sortDirection === 'asc') {
        return aVal > bVal ? 1 : -1;
      } else {
        return aVal < bVal ? 1 : -1;
      }
    });
    
    setDisplayedProducts(sorted);
  };

  const handleSort = (field) => {
    if (sortField === field) {
      // toggle direction
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('desc');
    }
  };

  const handleExport = async (format = 'csv') => {
    if (!selectedStoreId) return;
    
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/price-comparison/export/${selectedStoreId}?format=${format}`
      );
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const date = new Date().toISOString().split('T')[0];
      a.download = `price_comparison_${selectedStoreId}_${date}.${format}`;
      a.click();
    } catch (err) {
      console.error('Error exporting data:', err);
      alert('Failed to export data');
    }
  };

  // pick colors based on store type
  const getStoreColor = (storeType) => {
    const colors = {
      "Supermarket": "bg-red-500",
      "Discount Supermarket": "bg-yellow-500", 
      "Indian Grocery": "bg-purple-500",
      "Asian/Indian Grocery": "bg-green-500"
    };
    return colors[storeType] || "bg-gray-500";
  };

  const primaryStore = stores.find(s => s.is_primary);
  const competitorStores = stores.filter(s => !s.is_primary);
  
  // paginate displayed products
  const paginatedProducts = displayedProducts.slice(
    page * productsPerPage,
    (page + 1) * productsPerPage
  );

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800 text-white p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold mb-2 flex items-center gap-3">
            <ShoppingCart className="w-10 h-10 text-green-400" />
            Price Comparison Dashboard
          </h1>
          <p className="text-gray-300">
            Compare {primaryStore?.name || 'Made in India Grocery'} prices with competitors
          </p>
        </div>

        {/* Store Selector */}
        <div className="bg-slate-800/50 backdrop-blur rounded-xl p-6 mb-6 border border-slate-700">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <Store className="w-6 h-6 text-blue-400" />
              <h2 className="text-xl font-semibold">Select Competitor Store</h2>
            </div>
            <div className="flex items-center gap-2 text-sm text-gray-400">
              <Award className="w-4 h-4" />
              Primary Store: {primaryStore?.name || 'Loading...'}
              {primaryStore && (
                <span className="ml-2 text-green-400">
                  ({primaryStore.total_products} products)
                </span>
              )}
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {competitorStores.map(store => (
              <button
                key={store.id}
                onClick={() => {
                  setSelectedStoreId(store.id);
                  setPage(0);
                  setSelectedCategory('All');
                  setSearchQuery('');
                }}
                className={`p-4 rounded-lg border-2 transition-all ${
                  selectedStoreId === store.id
                    ? 'border-green-400 bg-green-400/10'
                    : 'border-slate-600 bg-slate-700/50 hover:border-slate-500'
                }`}
              >
                <div className="text-left">
                  <div className="font-semibold mb-1">{store.name}</div>
                  <div className="text-sm text-gray-400">
                     {store.matched_products} products matched
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    {store.location}
                  </div>
                  <div className={`inline-block px-2 py-1 rounded text-xs mt-2 ${getStoreColor(store.store_type)} bg-opacity-20`}>
                    {store.store_type}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Filters */}
        {comparisonData && (
          <div className="bg-slate-800/50 backdrop-blur rounded-xl p-4 mb-6 border border-slate-700">
            <div className="flex flex-col md:flex-row gap-4">
              {/* Category Filter */}
              <div className="flex items-center gap-2 flex-1">
                <Filter className="w-5 h-5 text-blue-400" />
                <select
                  value={selectedCategory}
                  onChange={(e) => setSelectedCategory(e.target.value)}
                  className="bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 flex-1"
                >
                  <option value="All">All Categories</option>
                  {comparisonData.categories?.map(cat => (
                    <option key={cat} value={cat}>{cat}</option>
                  ))}
                </select>
              </div>
              
              {/* Search */}
              <div className="flex items-center gap-2 flex-1">
                <Search className="w-5 h-5 text-blue-400" />
                <input
                  type="text"
                  placeholder="Search products..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 flex-1"
                />
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="bg-red-500/20 border border-red-500 rounded-xl p-4 mb-6 flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-400" />
            <span>{error}</span>
            <button 
              onClick={() => fetchComparisonData(selectedStoreId)}
              className="ml-auto px-3 py-1 bg-red-600 hover:bg-red-500 rounded transition-colors"
            >
              Retry
            </button>
          </div>
        )}

        {loading ? (
          <div className="flex flex-col justify-center items-center h-64">
            <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-green-400"></div>
            <p className="mt-4 text-gray-400">Loading comparison data...</p>
          </div>
        ) : comparisonData && (
          <>
            {/* Statistics Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
              <div className="bg-gradient-to-br from-green-600/20 to-green-700/20 backdrop-blur rounded-xl p-6 border border-green-500/30">
                <div className="flex items-center justify-between mb-2">
                  <Package className="w-8 h-8 text-green-400" />
                  <span className="text-2xl font-bold">
                    {displayedProducts.length}
                  </span>
                </div>
                <div className="text-sm text-gray-300">Products Shown</div>
              </div>

              <div className="bg-gradient-to-br from-blue-600/20 to-blue-700/20 backdrop-blur rounded-xl p-6 border border-blue-500/30">
                <div className="flex items-center justify-between mb-2">
                  <DollarSign className="w-8 h-8 text-blue-400" />
                  <span className="text-2xl font-bold">
                    {comparisonData.statistics.average_savings_percent.toFixed(1)}%
                  </span>
                </div>
                <div className="text-sm text-gray-300">Average Savings</div>
              </div>

              <div className="bg-gradient-to-br from-emerald-600/20 to-emerald-700/20 backdrop-blur rounded-xl p-6 border border-emerald-500/30">
                <div className="flex items-center justify-between mb-2">
                  <TrendingDown className="w-8 h-8 text-emerald-400" />
                  <span className="text-2xl font-bold">
                    {comparisonData.statistics.we_cheaper_count}
                  </span>
                </div>
                <div className="text-sm text-gray-300">We're Cheaper</div>
              </div>

              <div className="bg-gradient-to-br from-orange-600/20 to-orange-700/20 backdrop-blur rounded-xl p-6 border border-orange-500/30">
                <div className="flex items-center justify-between mb-2">
                  <TrendingUp className="w-8 h-8 text-orange-400" />
                  <span className="text-2xl font-bold">
                    {comparisonData.statistics.they_cheaper_count}
                  </span>
                </div>
                <div className="text-sm text-gray-300">They're Cheaper</div>
              </div>
            </div>

            {/* Win Rate Bar */}
            <div className="bg-slate-800/50 backdrop-blur rounded-xl p-6 mb-6 border border-slate-700">
              <h3 className="text-lg font-semibold mb-4">Price Competitiveness</h3>
              <div className="relative h-12 bg-slate-700 rounded-full overflow-hidden">
                <div 
                  className="absolute left-0 top-0 h-full bg-gradient-to-r from-green-500 to-green-400 flex items-center justify-start px-4"
                  style={{ width: `${comparisonData.statistics.we_cheaper_percent}%` }}
                >
                  {comparisonData.statistics.we_cheaper_percent > 15 && (
                    <span className="text-sm font-semibold">
                      {comparisonData.statistics.we_cheaper_percent.toFixed(1)}% Cheaper
                    </span>
                  )}
                </div>
                <div 
                  className="absolute right-0 top-0 h-full bg-gradient-to-l from-orange-500 to-orange-400 flex items-center justify-end px-4"
                  style={{ width: `${comparisonData.statistics.they_cheaper_percent}%` }}
                >
                  {comparisonData.statistics.they_cheaper_percent > 15 && (
                    <span className="text-sm font-semibold">
                      {comparisonData.statistics.they_cheaper_percent.toFixed(1)}% Higher
                    </span>
                  )}
                </div>
                {/* show percentages outside if bar is too small */}
                {comparisonData.statistics.we_cheaper_percent <= 15 && comparisonData.statistics.we_cheaper_percent > 0 && (
                  <div className="absolute left-2 top-1/2 -translate-y-1/2 text-xs text-white font-semibold z-10">
                    {comparisonData.statistics.we_cheaper_percent.toFixed(1)}%
                  </div>
                )}
                {comparisonData.statistics.they_cheaper_percent <= 15 && comparisonData.statistics.they_cheaper_percent > 0 && (
                  <div className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-white font-semibold z-10">
                    {comparisonData.statistics.they_cheaper_percent.toFixed(1)}%
                  </div>
                )}
              </div>
            </div>

            {/* Products Table */}
            <div className="bg-slate-800/50 backdrop-blur rounded-xl p-6 border border-slate-700">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-xl font-semibold flex items-center gap-2">
                  <TrendingDown className="w-6 h-6 text-green-400" />
                  Product Comparisons
                  <span className="text-sm text-gray-400 ml-2">
                    ({displayedProducts.length} products)
                  </span>
                </h3>
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => fetchComparisonData(selectedStoreId)}
                    className="p-2 bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors"
                  >
                    <RefreshCw className="w-5 h-5" />
                  </button>
                  <button
                    onClick={() => handleExport('csv')}
                    className="px-4 py-2 bg-green-600 hover:bg-green-500 rounded-lg transition-colors flex items-center gap-2"
                  >
                    <Download className="w-4 h-4" />
                    Export CSV
                  </button>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-slate-700 text-left">
                      <th className="pb-4 text-gray-400 font-medium">Product</th>
                      <th 
                        className="pb-4 text-gray-400 font-medium cursor-pointer hover:text-white"
                        onClick={() => handleSort('size')}
                      >
                        <div className="flex items-center gap-1">
                          Size
                          {sortField === 'size' && (
                            sortDirection === 'desc' ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />
                          )}
                        </div>
                      </th>
                      <th 
                        className="pb-4 text-gray-400 font-medium cursor-pointer hover:text-white"
                        onClick={() => handleSort('our_price')}
                      >
                        <div className="flex items-center gap-1">
                          Our Price
                          {sortField === 'our_price' && (
                            sortDirection === 'desc' ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />
                          )}
                        </div>
                      </th>
                      <th 
                        className="pb-4 text-gray-400 font-medium cursor-pointer hover:text-white"
                        onClick={() => handleSort('their_price')}
                      >
                        <div className="flex items-center gap-1">
                          Their Price
                          {sortField === 'their_price' && (
                            sortDirection === 'desc' ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />
                          )}
                        </div>
                      </th>
                      <th className="pb-4 text-gray-400 font-medium">Per 100g/ml</th>
                      <th 
                        className="pb-4 text-gray-400 font-medium cursor-pointer hover:text-white"
                        onClick={() => handleSort('savings')}
                      >
                        <div className="flex items-center gap-1">
                          Savings
                          {sortField === 'savings' && (
                            sortDirection === 'desc' ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />
                          )}
                        </div>
                      </th>
                      <th 
                        className="pb-4 text-gray-400 font-medium cursor-pointer hover:text-white"
                        onClick={() => handleSort('match')}
                      >
                        <div className="flex items-center gap-1">
                          Match
                          {sortField === 'match' && (
                            sortDirection === 'desc' ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />
                          )}
                        </div>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedProducts.map((product, idx) => (
                      <tr key={idx} className="border-b border-slate-700/50 hover:bg-slate-700/30 transition-colors">
                        <td className="py-4">
                          <div className="font-medium">{product.primary_product_name}</div>
                          {product.primary_product_name !== product.competitor_product_name && (
                            <div className="text-sm text-gray-400 mt-1">
                              → {product.competitor_product_name}
                            </div>
                          )}
                          <div className="text-xs text-gray-500 mt-1">
                            {product.category}
                          </div>
                        </td>
                        <td className="py-4 text-sm text-gray-400">
                          {product.primary_product_size || '-'}
                        </td>
                        <td className="py-4">
                          <span className={`px-3 py-1 rounded-lg font-semibold ${
                            product.savings > 0 
                              ? 'bg-green-500/20 text-green-400' 
                              : 'bg-slate-600/50 text-white'
                          }`}>
                            ${product.our_price.toFixed(2)}
                          </span>
                          {product.is_on_sale_primary && (
                            <span className="ml-2 text-xs text-yellow-400">SALE</span>
                          )}
                        </td>
                        <td className="py-4">
                          ${product.their_price.toFixed(2)}
                          {product.is_on_sale_competitor && (
                            <span className="ml-2 text-xs text-yellow-400">SALE</span>
                          )}
                        </td>
                        <td className="py-4 text-sm">
                          {product.our_normalized_price && product.their_normalized_price ? (
                            <div className="flex flex-col gap-1">
                              <span className={`${product.our_normalized_price < product.their_normalized_price ? 'text-green-400' : 'text-gray-400'}`}>
                                Us: ${product.our_normalized_price.toFixed(2)}
                              </span>
                              <span className="text-gray-400">
                                Them: ${product.their_normalized_price.toFixed(2)}
                              </span>
                            </div>
                          ) : (
                            <span className="text-gray-500">-</span>
                          )}
                        </td>
                        <td className="py-4">
                          <div className="flex items-center gap-2">
                            {product.savings > 0 ? (
                              <>
                                <TrendingDown className="w-4 h-4 text-green-400" />
                                <span className="text-green-400 font-semibold">
                                  ${Math.abs(product.savings).toFixed(2)} ({Math.abs(product.savings_percent).toFixed(1)}%)
                                </span>
                              </>
                            ) : product.savings < 0 ? (
                              <>
                                <TrendingUp className="w-4 h-4 text-orange-400" />
                                <span className="text-orange-400">
                                  ${Math.abs(product.savings).toFixed(2)} higher
                                </span>
                              </>
                            ) : (
                              <span className="text-gray-400">Same</span>
                            )}
                          </div>
                        </td>
                        <td className="py-4">
                          <div className="flex flex-col gap-1">
                            <div className="w-20 bg-slate-700 rounded-full h-2">
                              <div 
                                className={`h-2 rounded-full ${
                                  product.match_confidence >= 0.9 
                                    ? 'bg-green-500' 
                                    : product.match_confidence >= 0.75 
                                    ? 'bg-yellow-500' 
                                    : 'bg-orange-500'
                                }`}
                                style={{ width: `${product.match_confidence * 100}%` }}
                              />
                            </div>
                            <span className="text-xs text-gray-400">
                              {product.match_type} ({(product.match_confidence * 100).toFixed(0)}%)
                            </span>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              <div className="mt-6 flex justify-between items-center">
                <div className="text-sm text-gray-400">
                  Showing {page * productsPerPage + 1} to {Math.min((page + 1) * productsPerPage, displayedProducts.length)} of {displayedProducts.length} products
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage(p => Math.max(0, p - 1))}
                    disabled={page === 0}
                    className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setPage(p => p + 1)}
                    disabled={(page + 1) * productsPerPage >= displayedProducts.length}
                    className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Next
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default PriceComparisonDashboard;